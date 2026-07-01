#!/usr/bin/env python3
"""Diagnose fixed-period failures from side-prior-pressure score replacement."""

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

from trade_data.backtest import (  # noqa: E402
    enrich_trades_with_predictions,
    json_default,
    make_run_dir,
    prepare_analysis_predictions,
    read_trades_csv,
)


TRADE_KEY_COLUMNS = ["candidate", "month", "direction", "entry_decision_timestamp"]
DEFAULT_EXTRA_COLUMNS = [
    "combined_regime",
    "session_regime",
    "pred_side_balanced_dense_executable_long_best_adjusted_pnl",
    "pred_side_balanced_dense_executable_short_best_adjusted_pnl",
    "pred_side_prior_pressure_s0p5_long_best_adjusted_pnl",
    "pred_side_prior_pressure_s0p5_short_best_adjusted_pnl",
    "pred_side_prior_pressure_long_predicted_ev_overestimate_risk",
    "pred_side_prior_pressure_short_predicted_ev_overestimate_risk",
    "pred_side_prior_pressure_long_ev_overestimate_prediction_source",
    "pred_side_prior_pressure_short_ev_overestimate_prediction_source",
    "pred_side_prior_pressure_long_support_bucket",
    "pred_side_prior_pressure_short_support_bucket",
    "pred_side_prior_pressure_long_pressure_bucket",
    "pred_side_prior_pressure_short_pressure_bucket",
    "pred_side_prior_pressure_long_prior_support_bucket",
    "pred_side_prior_pressure_short_prior_support_bucket",
    "pred_side_prior_pressure_long_feature_pressure_bucket",
    "pred_side_prior_pressure_short_feature_pressure_bucket",
    "pred_side_prior_pressure_long_prior_downside_risk_score",
    "pred_side_prior_pressure_short_prior_downside_risk_score",
    "pred_side_prior_pressure_long_feature_pressure_score",
    "pred_side_prior_pressure_short_feature_pressure_score",
    "pred_side_prior_pressure_long_side_balance_signed_drift_for_trade",
    "pred_side_prior_pressure_short_side_balance_signed_drift_for_trade",
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


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values), default).fillna(default).astype(float)


def cumulative_max_drawdown(values: pd.Series) -> float:
    cumulative = values.astype(float).cumsum()
    if cumulative.empty:
        return 0.0
    return float((cumulative.cummax() - cumulative).max())


def bool_mean(frame: pd.DataFrame, column: str, default: bool = False) -> float:
    if column not in frame.columns:
        return float(default)
    series = frame[column]
    if series.empty:
        return float(default)
    if pd.api.types.is_bool_dtype(series):
        return float(series.fillna(default).astype(bool).mean())
    if pd.api.types.is_numeric_dtype(series):
        return float(series.fillna(float(default)).astype(float).ne(0.0).mean())
    normalized = series.astype(str).str.lower().str.strip()
    return float(normalized.isin({"true", "1", "yes", "y"}).mean())


def read_monthly_metrics(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "monthly_policy_metrics.csv"
    frame = pd.read_csv(path)
    required = {"family", "role", "month", "candidate"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    return frame


def trade_path(run_dir: Path, row: pd.Series) -> Path:
    return (
        run_dir
        / "trades"
        / str(row["family"])
        / str(row["candidate"])
        / f"{row['month']}.csv"
    )


def read_variant_trades(
    *,
    run_dir: Path,
    variant: str,
    predictions: pd.DataFrame,
    long_column: str,
    short_column: str,
    extra_prediction_columns: list[str],
) -> pd.DataFrame:
    monthly = read_monthly_metrics(run_dir)
    analysis_predictions = prepare_analysis_predictions(
        predictions,
        long_column,
        short_column,
        extra_prediction_columns,
    )
    frames: list[pd.DataFrame] = []
    missing_paths: list[Path] = []
    for _, row in monthly.iterrows():
        path = trade_path(run_dir, row)
        if not path.exists():
            missing_paths.append(path)
            continue
        trades = read_trades_csv(path)
        if trades.empty:
            continue
        enriched = enrich_trades_with_predictions(
            trades,
            analysis_predictions,
            extra_prediction_columns,
        )
        enriched.insert(0, "variant", variant)
        enriched.insert(1, "family", str(row["family"]))
        enriched.insert(2, "role", str(row["role"]))
        enriched.insert(3, "month", str(row["month"]))
        enriched.insert(4, "candidate", str(row["candidate"]))
        frames.append(enriched)
    if missing_paths:
        preview = ", ".join(str(path) for path in missing_paths[:5])
        suffix = "" if len(missing_paths) <= 5 else f" ... ({len(missing_paths)} missing)"
        raise FileNotFoundError(f"missing trade files: {preview}{suffix}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def selected_side_value(
    frame: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
    default: float = 0.0,
) -> pd.Series:
    direction = frame["direction"].astype(str).str.lower()
    long_values = numeric_series(frame, long_column, default=default)
    short_values = numeric_series(frame, short_column, default=default)
    return pd.Series(
        np.where(direction.eq("long"), long_values, short_values),
        index=frame.index,
    )


def selected_side_text(
    frame: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
    default: str = "missing",
) -> pd.Series:
    direction = frame["direction"].astype(str).str.lower()
    long_values = (
        frame[long_column].fillna(default).astype(str)
        if long_column in frame.columns
        else pd.Series(default, index=frame.index)
    )
    short_values = (
        frame[short_column].fillna(default).astype(str)
        if short_column in frame.columns
        else pd.Series(default, index=frame.index)
    )
    return pd.Series(
        np.where(direction.eq("long"), long_values, short_values),
        index=frame.index,
    )


def add_selected_side_features(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["selected_side_prior_pressure_risk"] = selected_side_value(
        output,
        long_column="pred_side_prior_pressure_long_predicted_ev_overestimate_risk",
        short_column="pred_side_prior_pressure_short_predicted_ev_overestimate_risk",
        default=np.nan,
    )
    output["selected_side_prior_downside_risk"] = selected_side_value(
        output,
        long_column="pred_side_prior_pressure_long_prior_downside_risk_score",
        short_column="pred_side_prior_pressure_short_prior_downside_risk_score",
    )
    output["selected_side_feature_pressure"] = selected_side_value(
        output,
        long_column="pred_side_prior_pressure_long_feature_pressure_score",
        short_column="pred_side_prior_pressure_short_feature_pressure_score",
    )
    output["selected_side_signed_drift"] = selected_side_value(
        output,
        long_column="pred_side_prior_pressure_long_side_balance_signed_drift_for_trade",
        short_column="pred_side_prior_pressure_short_side_balance_signed_drift_for_trade",
    )
    output["selected_side_base_score"] = selected_side_value(
        output,
        long_column="pred_side_balanced_dense_executable_long_best_adjusted_pnl",
        short_column="pred_side_balanced_dense_executable_short_best_adjusted_pnl",
        default=np.nan,
    )
    output["selected_side_side_prior_score"] = selected_side_value(
        output,
        long_column="pred_side_prior_pressure_s0p5_long_best_adjusted_pnl",
        short_column="pred_side_prior_pressure_s0p5_short_best_adjusted_pnl",
        default=np.nan,
    )
    output["selected_side_score_delta"] = (
        output["selected_side_side_prior_score"] - output["selected_side_base_score"]
    )
    output["selected_side_prediction_source"] = selected_side_text(
        output,
        long_column="pred_side_prior_pressure_long_ev_overestimate_prediction_source",
        short_column="pred_side_prior_pressure_short_ev_overestimate_prediction_source",
    )
    output["selected_side_support_bucket"] = selected_side_text(
        output,
        long_column="pred_side_prior_pressure_long_support_bucket",
        short_column="pred_side_prior_pressure_short_support_bucket",
    )
    output["selected_side_pressure_bucket"] = selected_side_text(
        output,
        long_column="pred_side_prior_pressure_long_pressure_bucket",
        short_column="pred_side_prior_pressure_short_pressure_bucket",
    )
    output["selected_side_prior_support_bucket"] = selected_side_text(
        output,
        long_column="pred_side_prior_pressure_long_prior_support_bucket",
        short_column="pred_side_prior_pressure_short_prior_support_bucket",
    )
    output["selected_side_feature_pressure_bucket"] = selected_side_text(
        output,
        long_column="pred_side_prior_pressure_long_feature_pressure_bucket",
        short_column="pred_side_prior_pressure_short_feature_pressure_bucket",
    )
    return output


def trade_key(frame: pd.DataFrame) -> pd.Series:
    normalized = frame.copy()
    normalized["entry_decision_timestamp"] = pd.to_datetime(
        normalized["entry_decision_timestamp"],
        utc=True,
    ).astype(str)
    return normalized[TRADE_KEY_COLUMNS].astype(str).agg("|".join, axis=1)


def add_replacement_status(
    base: pd.DataFrame,
    candidate: pd.DataFrame,
    *,
    base_label: str,
    candidate_label: str,
) -> pd.DataFrame:
    base_frame = base.copy()
    candidate_frame = candidate.copy()
    base_keys = set(trade_key(base_frame))
    candidate_keys = set(trade_key(candidate_frame))
    base_frame["_trade_key"] = trade_key(base_frame)
    candidate_frame["_trade_key"] = trade_key(candidate_frame)
    base_frame["replacement_status"] = np.where(
        base_frame["_trade_key"].isin(candidate_keys),
        "common",
        f"only_{base_label}",
    )
    candidate_frame["replacement_status"] = np.where(
        candidate_frame["_trade_key"].isin(base_keys),
        "common",
        f"only_{candidate_label}",
    )
    return pd.concat([base_frame, candidate_frame], ignore_index=True)


def summarize_slice(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "trade_count": 0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
        }
    pnl = numeric_series(frame, "adjusted_pnl")
    direction = frame["direction"].astype(str).str.lower()
    return {
        "trade_count": int(len(frame)),
        "total_pnl": float(pnl.sum()),
        "avg_pnl": float(pnl.mean()),
        "loss_pnl": float(pnl.where(pnl < 0.0, 0.0).sum()),
        "win_pnl": float(pnl.where(pnl > 0.0, 0.0).sum()),
        "win_rate": float(pnl.gt(0.0).mean()),
        "max_drawdown": cumulative_max_drawdown(pnl),
        "long_count": int(direction.eq("long").sum()),
        "short_count": int(direction.eq("short").sum()),
        "forced_exit_share": float(
            frame.get("exit_reason", pd.Series("", index=frame.index))
            .astype(str)
            .eq("forced_exit")
            .mean()
        ),
        "direction_error_rate": bool_mean(frame, "direction_error"),
        "no_edge_rate": bool_mean(frame, "no_edge_entry"),
        "exit_regret_sum": float(numeric_series(frame, "exit_regret").sum()),
        "ev_overestimate_realized_mean": float(
            numeric_series(frame, "ev_overestimate_vs_realized").mean()
        ),
        "selected_risk_mean": float(
            numeric_series(frame, "selected_side_prior_pressure_risk", default=np.nan)
            .dropna()
            .mean()
        )
        if numeric_series(frame, "selected_side_prior_pressure_risk", default=np.nan)
        .notna()
        .any()
        else float("nan"),
        "selected_prior_downside_risk_mean": float(
            numeric_series(frame, "selected_side_prior_downside_risk").mean()
        ),
        "selected_feature_pressure_mean": float(
            numeric_series(frame, "selected_side_feature_pressure").mean()
        ),
        "selected_signed_drift_mean": float(
            numeric_series(frame, "selected_side_signed_drift").mean()
        ),
        "selected_score_delta_mean": float(
            numeric_series(frame, "selected_side_score_delta", default=np.nan)
            .dropna()
            .mean()
        )
        if numeric_series(frame, "selected_side_score_delta", default=np.nan)
        .notna()
        .any()
        else float("nan"),
    }


def summarize_by(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(columns, keys, strict=True))
        row.update(summarize_slice(group.sort_values("entry_decision_timestamp")))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [*columns, "total_pnl"],
        ascending=[True] * len(columns) + [True],
    ).reset_index(drop=True)


def replacement_delta_summary(
    path_summary: pd.DataFrame,
    *,
    base_label: str,
    candidate_label: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    only_base = f"only_{base_label}"
    only_candidate = f"only_{candidate_label}"
    for candidate, group in path_summary.groupby("candidate", dropna=False):
        status_pnl = group.set_index("replacement_status")["total_pnl"].to_dict()
        status_count = group.set_index("replacement_status")["trade_count"].to_dict()
        rows.append(
            {
                "candidate": candidate,
                "common_pnl": float(status_pnl.get("common", 0.0)),
                "only_base_pnl": float(status_pnl.get(only_base, 0.0)),
                "only_candidate_pnl": float(status_pnl.get(only_candidate, 0.0)),
                "replacement_delta_pnl": float(
                    status_pnl.get(only_candidate, 0.0) - status_pnl.get(only_base, 0.0)
                ),
                "common_count": int(status_count.get("common", 0)),
                "only_base_count": int(status_count.get(only_base, 0)),
                "only_candidate_count": int(status_count.get(only_candidate, 0)),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["replacement_delta_pnl", "candidate"],
        ascending=[True, True],
    ).reset_index(drop=True)


def variant_path_delta_summary(
    variant_path_summary: pd.DataFrame,
    *,
    base_label: str,
    candidate_label: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    only_base = f"only_{base_label}"
    only_candidate = f"only_{candidate_label}"
    for candidate, group in variant_path_summary.groupby("candidate", dropna=False):
        keyed = group.set_index(["variant", "replacement_status"])
        pnl = keyed["total_pnl"].to_dict()
        counts = keyed["trade_count"].to_dict()
        base_common_pnl = float(pnl.get((base_label, "common"), 0.0))
        candidate_common_pnl = float(pnl.get((candidate_label, "common"), 0.0))
        only_base_pnl = float(pnl.get((base_label, only_base), 0.0))
        only_candidate_pnl = float(pnl.get((candidate_label, only_candidate), 0.0))
        base_common_count = int(counts.get((base_label, "common"), 0))
        candidate_common_count = int(counts.get((candidate_label, "common"), 0))
        only_base_count = int(counts.get((base_label, only_base), 0))
        only_candidate_count = int(counts.get((candidate_label, only_candidate), 0))
        base_total_pnl = base_common_pnl + only_base_pnl
        candidate_total_pnl = candidate_common_pnl + only_candidate_pnl
        base_total_count = base_common_count + only_base_count
        candidate_total_count = candidate_common_count + only_candidate_count
        rows.append(
            {
                "candidate": candidate,
                "base_common_pnl": base_common_pnl,
                "candidate_common_pnl": candidate_common_pnl,
                "common_entry_delta_pnl": candidate_common_pnl - base_common_pnl,
                "only_base_pnl": only_base_pnl,
                "only_candidate_pnl": only_candidate_pnl,
                "replacement_delta_pnl": only_candidate_pnl - only_base_pnl,
                "base_total_pnl": base_total_pnl,
                "candidate_total_pnl": candidate_total_pnl,
                "total_delta_pnl": candidate_total_pnl - base_total_pnl,
                "base_common_count": base_common_count,
                "candidate_common_count": candidate_common_count,
                "only_base_count": only_base_count,
                "only_candidate_count": only_candidate_count,
                "base_total_count": base_total_count,
                "candidate_total_count": candidate_total_count,
                "trade_count_delta": candidate_total_count - base_total_count,
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["total_delta_pnl", "candidate"],
        ascending=[True, True],
    ).reset_index(drop=True)


def build_diagnostics(args: argparse.Namespace) -> Path:
    predictions = pd.read_parquet(args.predictions)
    extra_columns = list(dict.fromkeys([*DEFAULT_EXTRA_COLUMNS, *parse_csv(args.extra_columns)]))
    base = read_variant_trades(
        run_dir=args.base_run_dir,
        variant=args.base_label,
        predictions=predictions,
        long_column=args.base_long_column,
        short_column=args.base_short_column,
        extra_prediction_columns=extra_columns,
    )
    candidate = read_variant_trades(
        run_dir=args.candidate_run_dir,
        variant=args.candidate_label,
        predictions=predictions,
        long_column=args.candidate_long_column,
        short_column=args.candidate_short_column,
        extra_prediction_columns=extra_columns,
    )
    base = add_selected_side_features(base)
    candidate = add_selected_side_features(candidate)
    combined = add_replacement_status(
        base,
        candidate,
        base_label=args.base_label,
        candidate_label=args.candidate_label,
    )

    variant_summary = summarize_by(combined, ["variant", "candidate"])
    path_summary = summarize_by(combined, ["candidate", "replacement_status"])
    variant_path_summary = summarize_by(
        combined,
        ["candidate", "variant", "replacement_status"],
    )
    delta_summary = replacement_delta_summary(
        path_summary,
        base_label=args.base_label,
        candidate_label=args.candidate_label,
    )
    path_delta_summary = variant_path_delta_summary(
        variant_path_summary,
        base_label=args.base_label,
        candidate_label=args.candidate_label,
    )
    month_path = summarize_by(combined, ["candidate", "month", "replacement_status"])
    context_path = summarize_by(
        combined,
        [
            "candidate",
            "replacement_status",
            "direction",
            "combined_regime",
            "session_regime",
        ],
    )
    risk_bucket = summarize_by(
        combined,
        [
            "candidate",
            "replacement_status",
            "selected_side_support_bucket",
            "selected_side_pressure_bucket",
            "selected_side_prior_support_bucket",
            "selected_side_feature_pressure_bucket",
        ],
    )
    worst_trades = combined.sort_values("adjusted_pnl").head(args.top_n).reset_index(drop=True)

    run_dir = make_run_dir(args.output_dir, args.label)
    combined.to_csv(run_dir / "combined_enriched_trades.csv", index=False)
    variant_summary.to_csv(run_dir / "variant_summary.csv", index=False)
    path_summary.to_csv(run_dir / "replacement_path_summary.csv", index=False)
    variant_path_summary.to_csv(run_dir / "variant_replacement_path_summary.csv", index=False)
    delta_summary.to_csv(run_dir / "replacement_delta_summary.csv", index=False)
    path_delta_summary.to_csv(run_dir / "path_delta_summary.csv", index=False)
    month_path.to_csv(run_dir / "month_replacement_path_summary.csv", index=False)
    context_path.to_csv(run_dir / "context_replacement_path_summary.csv", index=False)
    risk_bucket.to_csv(run_dir / "risk_bucket_replacement_path_summary.csv", index=False)
    worst_trades.to_csv(run_dir / "worst_trades.csv", index=False)
    config = {
        "base_run_dir": args.base_run_dir,
        "candidate_run_dir": args.candidate_run_dir,
        "predictions": args.predictions,
        "base_label": args.base_label,
        "candidate_label": args.candidate_label,
        "base_long_column": args.base_long_column,
        "base_short_column": args.base_short_column,
        "candidate_long_column": args.candidate_long_column,
        "candidate_short_column": args.candidate_short_column,
        "extra_columns": extra_columns,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Replacement delta:")
    print(delta_summary.to_string(index=False))
    print("\nPath delta:")
    print(path_delta_summary.to_string(index=False))
    print("\nWorst replacement contexts:")
    print(
        context_path[
            [
                "candidate",
                "replacement_status",
                "direction",
                "combined_regime",
                "session_regime",
                "trade_count",
                "total_pnl",
                "selected_risk_mean",
            ]
        ]
        .sort_values(["total_pnl", "trade_count"], ascending=[True, False])
        .head(args.top_n)
        .to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-run-dir", type=Path, required=True)
    parser.add_argument("--candidate-run-dir", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--base-label", default="base")
    parser.add_argument("--candidate-label", default="side_prior")
    parser.add_argument(
        "--base-long-column",
        default="pred_side_balanced_dense_executable_long_best_adjusted_pnl",
    )
    parser.add_argument(
        "--base-short-column",
        default="pred_side_balanced_dense_executable_short_best_adjusted_pnl",
    )
    parser.add_argument(
        "--candidate-long-column",
        default="pred_side_prior_pressure_s0p5_long_best_adjusted_pnl",
    )
    parser.add_argument(
        "--candidate-short-column",
        default="pred_side_prior_pressure_s0p5_short_best_adjusted_pnl",
    )
    parser.add_argument("--extra-columns", default="")
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_side_prior_pressure_failure_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
