#!/usr/bin/env python3
"""Break down EV-overestimate risk by side and context."""

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

from entry_ev_overestimate_risk_selector import (  # noqa: E402
    DEFAULT_TARGET,
    build_chronological_ev_risk,
    parse_csv,
    read_component_frame,
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


def bucketize_context(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    support = pd.to_numeric(output.get("prior_downside_support_weight", 0.0), errors="coerce").fillna(0.0)
    pressure = pd.to_numeric(output.get("feature_pressure_score", 0.0), errors="coerce").fillna(0.0)
    drift = pd.to_numeric(
        output.get("side_balance_signed_drift_for_trade", 0.0),
        errors="coerce",
    ).fillna(0.0)
    prior_risk = pd.to_numeric(output.get("prior_downside_risk_score", 0.0), errors="coerce").fillna(0.0)
    output["prior_support_bucket"] = pd.cut(
        support,
        bins=[-np.inf, 0.0, 0.2, 0.5, np.inf],
        labels=["missing", "low", "medium", "high"],
        right=True,
    ).astype(str)
    output["feature_pressure_bucket"] = pd.cut(
        pressure,
        bins=[-np.inf, 0.25, 0.5, 0.7, np.inf],
        labels=["low", "medium", "high", "extreme"],
        right=False,
    ).astype(str)
    output["prior_downside_bucket"] = pd.cut(
        prior_risk,
        bins=[-np.inf, 0.0, 0.2, 0.4, np.inf],
        labels=["zero", "low", "medium", "high"],
        right=True,
    ).astype(str)
    output["side_drift_bucket"] = np.select(
        [drift <= -0.05, drift >= 0.05],
        ["negative", "positive"],
        default="neutral",
    )
    return output


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    values = values.astype(float)
    weights = weights.astype(float)
    valid = values.notna() & np.isfinite(values) & weights.gt(0.0)
    if not bool(valid.any()):
        return float("nan")
    return float(np.average(values[valid], weights=weights[valid]))


def summarize_group(
    group: pd.DataFrame,
    *,
    target: str,
    risk_threshold: float,
) -> dict[str, Any]:
    pnl = group["adjusted_pnl"].astype(float)
    risk = pd.to_numeric(group["predicted_ev_overestimate_risk"], errors="coerce")
    available = group["ev_overestimate_prediction_available"].astype(bool)
    high_risk = available & risk.ge(risk_threshold)
    target_values = group[target].astype(bool)
    rows = int(len(group))
    prediction_count = int(available.sum())
    return {
        "row_count": rows,
        "total_pnl": float(pnl.sum()),
        "avg_pnl": float(pnl.mean()) if rows else 0.0,
        "win_rate": float(pnl.gt(0.0).mean()) if rows else 0.0,
        "target_rate": float(target_values.mean()) if rows else 0.0,
        "target_true_pnl": float(pnl.where(target_values, 0.0).sum()),
        "target_false_pnl": float(pnl.where(~target_values, 0.0).sum()),
        "prediction_count": prediction_count,
        "prediction_coverage": float(prediction_count / rows) if rows else 0.0,
        "predicted_risk_mean": float(risk[available].mean()) if prediction_count else float("nan"),
        "high_risk_count": int(high_risk.sum()),
        "high_risk_share": float(high_risk.mean()) if rows else 0.0,
        "high_risk_pnl": float(pnl.where(high_risk, 0.0).sum()),
        "low_or_unknown_risk_pnl": float(pnl.where(~high_risk, 0.0).sum()),
        "high_risk_target_rate": float(target_values[high_risk].mean())
        if bool(high_risk.any())
        else float("nan"),
    }


def summarize_by(
    frame: pd.DataFrame,
    *,
    group_columns: list[str],
    target: str,
    risk_threshold: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(group_columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_columns, keys, strict=True))
        row.update(summarize_group(group, target=target, risk_threshold=risk_threshold))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["high_risk_pnl", "total_pnl", "row_count"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def build_role_contrast(
    role_context: pd.DataFrame,
    *,
    context_columns: list[str],
) -> pd.DataFrame:
    if role_context.empty:
        return pd.DataFrame()
    value_columns = [
        "row_count",
        "total_pnl",
        "target_rate",
        "predicted_risk_mean",
        "high_risk_count",
        "high_risk_share",
        "high_risk_pnl",
    ]
    pivot = role_context.pivot_table(
        index=context_columns,
        columns="role",
        values=value_columns,
        aggfunc="first",
    )
    pivot.columns = [f"{role}_{metric}" for metric, role in pivot.columns]
    contrast = pivot.reset_index()
    high_pnl_cols = [column for column in contrast.columns if column.endswith("_high_risk_pnl")]
    for column in high_pnl_cols:
        contrast[column] = pd.to_numeric(contrast[column], errors="coerce").fillna(0.0)
    fresh_col = "fresh2024_validation_high_risk_pnl"
    refit_col = "refit2025_validation_high_risk_pnl"
    cal_col = "cal2024_calibration_validation_high_risk_pnl"
    for column in [fresh_col, refit_col, cal_col]:
        if column not in contrast.columns:
            contrast[column] = 0.0
    contrast["fresh_minus_refit_high_risk_pnl"] = contrast[fresh_col] - contrast[refit_col]
    contrast["all_validation_high_risk_pnl"] = contrast[high_pnl_cols].sum(axis=1)
    return contrast.sort_values(
        ["fresh_minus_refit_high_risk_pnl", "all_validation_high_risk_pnl"],
    ).reset_index(drop=True)


def build_diagnostics(args: argparse.Namespace) -> Path:
    group_columns = parse_csv(args.group_columns)
    validation_roles = parse_csv(args.validation_roles)
    context_columns = parse_csv(args.context_columns)
    if not group_columns:
        raise ValueError("--group-columns must not be empty")
    if not validation_roles:
        raise ValueError("--validation-roles must not be empty")
    if not context_columns:
        raise ValueError("--context-columns must not be empty")

    component = read_component_frame(
        args.component_targets,
        target=args.target,
        group_columns=group_columns,
    )
    risk_frame = build_chronological_ev_risk(
        component,
        target=args.target,
        group_columns=group_columns,
        prior_strength=args.prior_strength,
        min_group_support=args.min_group_support,
    )
    risk_frame = bucketize_context(risk_frame)
    validation = risk_frame[risk_frame["role"].isin(validation_roles)].copy()
    missing_context = sorted(set(context_columns) - set(validation.columns))
    if missing_context:
        raise ValueError(f"context columns missing: {', '.join(missing_context)}")
    if validation.empty:
        raise ValueError("no validation rows matched --validation-roles")

    role_context = summarize_by(
        validation,
        group_columns=["role", *context_columns],
        target=args.target,
        risk_threshold=args.risk_threshold,
    )
    context = summarize_by(
        validation,
        group_columns=context_columns,
        target=args.target,
        risk_threshold=args.risk_threshold,
    )
    candidate_context = summarize_by(
        validation,
        group_columns=["candidate", *context_columns],
        target=args.target,
        risk_threshold=args.risk_threshold,
    )
    contrast = build_role_contrast(role_context, context_columns=context_columns)

    run_dir = make_run_dir(args.output_dir, args.label)
    validation.to_csv(run_dir / "ev_overestimate_context_trades.csv", index=False)
    role_context.to_csv(run_dir / "role_context_ev_overestimate_summary.csv", index=False)
    context.to_csv(run_dir / "context_ev_overestimate_summary.csv", index=False)
    candidate_context.to_csv(
        run_dir / "candidate_context_ev_overestimate_summary.csv",
        index=False,
    )
    contrast.to_csv(run_dir / "role_context_high_risk_contrast.csv", index=False)
    config = {
        "component_targets": args.component_targets,
        "target": args.target,
        "group_columns": group_columns,
        "validation_roles": validation_roles,
        "context_columns": context_columns,
        "prior_strength": args.prior_strength,
        "min_group_support": args.min_group_support,
        "risk_threshold": args.risk_threshold,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Worst context high-risk summary:")
    print(
        context[
            [
                *context_columns,
                "row_count",
                "total_pnl",
                "target_rate",
                "predicted_risk_mean",
                "high_risk_count",
                "high_risk_pnl",
            ]
        ]
        .head(args.top_n)
        .to_string(index=False)
    )
    print("\nRole contrast:")
    contrast_cols = [
        *context_columns,
        "fresh2024_validation_high_risk_pnl",
        "refit2025_validation_high_risk_pnl",
        "cal2024_calibration_validation_high_risk_pnl",
        "fresh_minus_refit_high_risk_pnl",
        "all_validation_high_risk_pnl",
    ]
    print(contrast[contrast_cols].head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-targets", type=Path, required=True)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--group-columns", default="support_bucket,pressure_bucket")
    parser.add_argument(
        "--context-columns",
        default="direction,support_bucket,pressure_bucket,prior_support_bucket,feature_pressure_bucket,side_drift_bucket",
    )
    parser.add_argument("--validation-roles", required=True)
    parser.add_argument("--prior-strength", type=float, default=5.0)
    parser.add_argument("--min-group-support", type=int, default=3)
    parser.add_argument("--risk-threshold", type=float, default=0.50)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_overestimate_context_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
