#!/usr/bin/env python3
"""Audit prior-only signals for harmful short replacement trades."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


CONDITION_SPECS: tuple[tuple[str, str], ...] = (
    ("prior_alert_ge1", "prior short side-drift alert count >= 1"),
    ("prior_alert_loss_bias_ge10", "prior alert loss-bias sum >= 10"),
    ("prior_pred_short_bias_max_ge_0p30", "prior max pred-short label bias >= 0.30"),
    ("prior_pred_short_bias_mean_ge_0p20", "prior mean pred-short label bias >= 0.20"),
    ("prior_pred_short_share_mean_ge_0p70", "prior mean pred-EV short share >= 0.70"),
    ("prior_pred_match_mean_lt_0p45", "prior mean pred/nonflat-label match < 0.45"),
    ("prior_short_pnl_lt_0", "prior selected short PnL < 0"),
    ("prior_short_min_pnl_lt_m25", "prior selected short worst month PnL < -25"),
    ("prior_short_ev_over_ge25", "prior selected short EV overestimate mean >= 25"),
    ("prior_alert_or_pred_bias", "prior alert or prior max pred-short bias >= 0.30"),
)


@dataclass(frozen=True)
class PriorMetrics:
    prior_alert_count: int
    prior_alert_months: int
    prior_alert_loss_bias_sum: float
    prior_alert_min_total_pnl: float
    prior_alert_max_side_bias: float
    same_month_alert_count: int
    same_month_alert_loss_bias_sum: float
    prior_prediction_rows: float
    prior_pred_short_bias_mean: float
    prior_pred_short_bias_max: float
    prior_pred_short_share_mean: float
    prior_actual_short_share_mean: float
    prior_pred_match_rate_mean: float
    prior_pred_side_score_mean: float
    prior_short_trade_count: float
    prior_short_pnl_sum: float
    prior_short_min_month_pnl: float
    prior_short_ev_overestimate_mean: float


def parse_csv_paths(value: str) -> list[Path]:
    paths = [Path(part.strip()) for part in value.split(",") if part.strip()]
    if not paths:
        raise argparse.ArgumentTypeError("at least one path is required")
    return paths


def local_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def read_csv_many(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        return pd.DataFrame()
    frames = []
    for path in paths:
        frames.append(pd.read_csv(path))
    return pd.concat(frames, ignore_index=True, sort=False)


def bool_series(series: pd.Series) -> pd.Series:
    def convert(value: Any) -> bool:
        if pd.isna(value):
            return False
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes", "y"}
        return bool(value)

    return series.map(convert).astype(bool)


def normalize_replacement_rows(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "candidate",
        "window",
        "month",
        "direction",
        "delta_status",
        "candidate_adjusted_pnl",
        "combined_regime",
        "session_regime",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("replacement rows missing columns: " + ", ".join(missing))
    output = frame.copy()
    output["month"] = output["month"].astype(str)
    output["direction"] = output["direction"].astype(str).str.lower()
    output["delta_status"] = output["delta_status"].astype(str)
    output["combined_regime"] = output["combined_regime"].astype(str)
    output["session_regime"] = output["session_regime"].astype(str)
    output["candidate_adjusted_pnl"] = pd.to_numeric(
        output["candidate_adjusted_pnl"],
        errors="raise",
    )
    if "is_loss" not in output.columns:
        output["is_loss"] = output["candidate_adjusted_pnl"] < 0
    else:
        output["is_loss"] = bool_series(output["is_loss"])
    return output


def normalize_side_drift_alerts(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    required = {
        "month",
        "combined_regime",
        "session_regime",
        "side",
        "is_alert",
        "loss_bias_score",
        "total_adjusted_pnl",
        "side_share_bias",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("side drift alerts missing columns: " + ", ".join(missing))
    output = frame.copy()
    output["month"] = output["month"].astype(str)
    output["combined_regime"] = output["combined_regime"].astype(str)
    output["session_regime"] = output["session_regime"].astype(str)
    output["side"] = output["side"].astype(str).str.lower()
    output["is_alert"] = bool_series(output["is_alert"])
    for column in ["loss_bias_score", "total_adjusted_pnl", "side_share_bias"]:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    return output


def normalize_prediction_group_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    output = frame.copy()
    if "month" not in output.columns:
        if "dataset_month" not in output.columns:
            raise ValueError("prediction group summary missing month or dataset_month")
        output = output.rename(columns={"dataset_month": "month"})
    required = {
        "month",
        "combined_regime",
        "session_regime",
        "prediction_rows",
        "pred_ev_short_share",
        "actual_label_short_share",
        "pred_short_minus_actual_label_short_share",
        "pred_ev_matches_nonflat_label_rate",
        "pred_side_score_mean",
    }
    missing = sorted(required - set(output.columns))
    if missing:
        raise ValueError("prediction group summary missing columns: " + ", ".join(missing))
    output["month"] = output["month"].astype(str)
    output["combined_regime"] = output["combined_regime"].astype(str)
    output["session_regime"] = output["session_regime"].astype(str)
    for column in required - {"month", "combined_regime", "session_regime"}:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    return output


def normalize_selected_trade_group_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    required = {
        "month",
        "combined_regime",
        "session_regime",
        "direction_side_name",
        "trade_count",
        "total_adjusted_pnl",
        "ev_overestimate_vs_realized_mean",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("selected trade group summary missing columns: " + ", ".join(missing))
    output = frame.copy()
    output["month"] = output["month"].astype(str)
    output["combined_regime"] = output["combined_regime"].astype(str)
    output["session_regime"] = output["session_regime"].astype(str)
    output["direction_side_name"] = output["direction_side_name"].astype(str).str.lower()
    for column in ["trade_count", "total_adjusted_pnl", "ev_overestimate_vs_realized_mean"]:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    return output


def available_months(*frames: pd.DataFrame) -> list[str]:
    months: set[str] = set()
    for frame in frames:
        if not frame.empty and "month" in frame.columns:
            months.update(frame["month"].astype(str).unique())
    return sorted(months)


def recent_prior_months(months: list[str], target_month: str, count: int) -> list[str]:
    prior = [month for month in months if month < target_month]
    return prior[-count:] if count > 0 else prior


def row_prior_metrics(
    row: pd.Series,
    *,
    months: list[str],
    side_drift_alerts: pd.DataFrame,
    prediction_groups: pd.DataFrame,
    selected_groups: pd.DataFrame,
    recent_month_count: int,
) -> PriorMetrics:
    target_month = str(row["month"])
    prior_months = recent_prior_months(months, target_month, recent_month_count)
    context_mask = (
        lambda frame: frame["combined_regime"].eq(row["combined_regime"])
        & frame["session_regime"].eq(row["session_regime"])
    )

    if side_drift_alerts.empty:
        prior_alerts = pd.DataFrame()
        same_alerts = pd.DataFrame()
    else:
        short_alerts = side_drift_alerts[
            side_drift_alerts["side"].eq("short") & side_drift_alerts["is_alert"]
        ]
        prior_alerts = short_alerts[
            short_alerts["month"].isin(prior_months) & context_mask(short_alerts)
        ]
        same_alerts = short_alerts[
            short_alerts["month"].eq(target_month) & context_mask(short_alerts)
        ]

    if prediction_groups.empty:
        prior_predictions = pd.DataFrame()
    else:
        prior_predictions = prediction_groups[
            prediction_groups["month"].isin(prior_months) & context_mask(prediction_groups)
        ]

    if selected_groups.empty:
        prior_selected = pd.DataFrame()
    else:
        prior_selected = selected_groups[
            selected_groups["direction_side_name"].eq("short")
            & selected_groups["month"].isin(prior_months)
            & context_mask(selected_groups)
        ]

    return PriorMetrics(
        prior_alert_count=int(len(prior_alerts)),
        prior_alert_months=int(prior_alerts["month"].nunique()) if not prior_alerts.empty else 0,
        prior_alert_loss_bias_sum=float(prior_alerts["loss_bias_score"].sum()) if not prior_alerts.empty else 0.0,
        prior_alert_min_total_pnl=(
            float(prior_alerts["total_adjusted_pnl"].min()) if not prior_alerts.empty else float("nan")
        ),
        prior_alert_max_side_bias=(
            float(prior_alerts["side_share_bias"].max()) if not prior_alerts.empty else float("nan")
        ),
        same_month_alert_count=int(len(same_alerts)),
        same_month_alert_loss_bias_sum=(
            float(same_alerts["loss_bias_score"].sum()) if not same_alerts.empty else 0.0
        ),
        prior_prediction_rows=(
            float(prior_predictions["prediction_rows"].sum()) if not prior_predictions.empty else 0.0
        ),
        prior_pred_short_bias_mean=(
            float(prior_predictions["pred_short_minus_actual_label_short_share"].mean())
            if not prior_predictions.empty
            else float("nan")
        ),
        prior_pred_short_bias_max=(
            float(prior_predictions["pred_short_minus_actual_label_short_share"].max())
            if not prior_predictions.empty
            else float("nan")
        ),
        prior_pred_short_share_mean=(
            float(prior_predictions["pred_ev_short_share"].mean())
            if not prior_predictions.empty
            else float("nan")
        ),
        prior_actual_short_share_mean=(
            float(prior_predictions["actual_label_short_share"].mean())
            if not prior_predictions.empty
            else float("nan")
        ),
        prior_pred_match_rate_mean=(
            float(prior_predictions["pred_ev_matches_nonflat_label_rate"].mean())
            if not prior_predictions.empty
            else float("nan")
        ),
        prior_pred_side_score_mean=(
            float(prior_predictions["pred_side_score_mean"].mean())
            if not prior_predictions.empty
            else float("nan")
        ),
        prior_short_trade_count=(
            float(prior_selected["trade_count"].sum()) if not prior_selected.empty else 0.0
        ),
        prior_short_pnl_sum=(
            float(prior_selected["total_adjusted_pnl"].sum()) if not prior_selected.empty else 0.0
        ),
        prior_short_min_month_pnl=(
            float(prior_selected["total_adjusted_pnl"].min()) if not prior_selected.empty else float("nan")
        ),
        prior_short_ev_overestimate_mean=(
            float(prior_selected["ev_overestimate_vs_realized_mean"].mean())
            if not prior_selected.empty
            else float("nan")
        ),
    )


def enrich_replacement_rows(
    replacement_rows: pd.DataFrame,
    *,
    side_drift_alerts: pd.DataFrame,
    prediction_groups: pd.DataFrame,
    selected_groups: pd.DataFrame,
    recent_month_count: int,
) -> pd.DataFrame:
    rows = normalize_replacement_rows(replacement_rows)
    alerts = normalize_side_drift_alerts(side_drift_alerts)
    predictions = normalize_prediction_group_summary(prediction_groups)
    selected = normalize_selected_trade_group_summary(selected_groups)
    months = available_months(rows, alerts, predictions, selected)
    metric_rows = [
        row_prior_metrics(
            row,
            months=months,
            side_drift_alerts=alerts,
            prediction_groups=predictions,
            selected_groups=selected,
            recent_month_count=recent_month_count,
        )
        for _, row in rows.iterrows()
    ]
    metrics = pd.DataFrame([metric.__dict__ for metric in metric_rows])
    output = pd.concat([rows.reset_index(drop=True), metrics], axis=1)
    add_conditions(output)
    return output


def add_conditions(frame: pd.DataFrame) -> None:
    frame["prior_alert_ge1"] = frame["prior_alert_count"].ge(1)
    frame["prior_alert_loss_bias_ge10"] = frame["prior_alert_loss_bias_sum"].ge(10.0)
    frame["prior_pred_short_bias_max_ge_0p30"] = frame["prior_pred_short_bias_max"].ge(0.30)
    frame["prior_pred_short_bias_mean_ge_0p20"] = frame["prior_pred_short_bias_mean"].ge(0.20)
    frame["prior_pred_short_share_mean_ge_0p70"] = frame["prior_pred_short_share_mean"].ge(0.70)
    frame["prior_pred_match_mean_lt_0p45"] = frame["prior_pred_match_rate_mean"].lt(0.45)
    frame["prior_short_pnl_lt_0"] = frame["prior_short_pnl_sum"].lt(0.0)
    frame["prior_short_min_pnl_lt_m25"] = frame["prior_short_min_month_pnl"].lt(-25.0)
    frame["prior_short_ev_over_ge25"] = frame["prior_short_ev_overestimate_mean"].ge(25.0)
    frame["prior_alert_or_pred_bias"] = (
        frame["prior_alert_ge1"] | frame["prior_pred_short_bias_max_ge_0p30"]
    )


def bool_sum(series: pd.Series) -> int:
    return int(bool_series(series).sum())


def condition_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    summary_rows: list[dict[str, Any]] = []
    grouped = rows.groupby(["candidate", "window"], dropna=False)
    for (candidate, window), group in grouped:
        total_rows = len(group)
        total_pnl = float(group["candidate_adjusted_pnl"].sum())
        total_loss_count = int(group["is_loss"].sum())
        for condition_name, description in CONDITION_SPECS:
            covered = group[group[condition_name]]
            uncovered = group[~group[condition_name]]
            summary_rows.append(
                {
                    "candidate": candidate,
                    "window": window,
                    "condition": condition_name,
                    "description": description,
                    "total_rows": total_rows,
                    "total_pnl": total_pnl,
                    "total_loss_count": total_loss_count,
                    "covered_rows": len(covered),
                    "covered_pnl": float(covered["candidate_adjusted_pnl"].sum()),
                    "covered_loss_count": int(covered["is_loss"].sum()),
                    "uncovered_rows": len(uncovered),
                    "uncovered_pnl": float(uncovered["candidate_adjusted_pnl"].sum()),
                    "uncovered_loss_count": int(uncovered["is_loss"].sum()),
                    "pnl_after_deleting_covered": float(
                        uncovered["candidate_adjusted_pnl"].sum()
                    ),
                }
            )
    return pd.DataFrame(summary_rows).sort_values(
        ["candidate", "window", "uncovered_pnl", "condition"]
    )


def context_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    return (
        rows.groupby(
            ["candidate", "window", "combined_regime", "session_regime"],
            dropna=False,
        )
        .agg(
            rows=("candidate_adjusted_pnl", "size"),
            total_pnl=("candidate_adjusted_pnl", "sum"),
            loss_count=("is_loss", bool_sum),
            prior_alert_rows=("prior_alert_ge1", bool_sum),
            prior_alert_or_bias_rows=("prior_alert_or_pred_bias", bool_sum),
            prior_prediction_rows=("prior_prediction_rows", "mean"),
            prior_pred_short_bias_mean=("prior_pred_short_bias_mean", "mean"),
            prior_pred_short_bias_max=("prior_pred_short_bias_max", "mean"),
            prior_pred_short_share_mean=("prior_pred_short_share_mean", "mean"),
            prior_pred_match_rate_mean=("prior_pred_match_rate_mean", "mean"),
            prior_short_trade_count=("prior_short_trade_count", "mean"),
            prior_short_pnl_sum=("prior_short_pnl_sum", "mean"),
            prior_short_ev_overestimate_mean=("prior_short_ev_overestimate_mean", "mean"),
            same_month_alert_rows=("same_month_alert_count", "sum"),
        )
        .reset_index()
        .sort_values(["candidate", "window", "total_pnl", "rows"])
    )


def top_uncovered_losses(rows: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    uncovered = rows[~rows["prior_alert_or_pred_bias"]].copy()
    columns = [
        "candidate",
        "window",
        "month",
        "entry_decision_timestamp",
        "candidate_adjusted_pnl",
        "combined_regime",
        "session_regime",
        "prior_alert_count",
        "prior_pred_short_bias_max",
        "prior_pred_short_share_mean",
        "prior_pred_match_rate_mean",
        "prior_short_pnl_sum",
        "prior_short_trade_count",
        "pred_taken_ev",
        "ev_overestimate_vs_realized",
    ]
    columns = [column for column in columns if column in uncovered.columns]
    return uncovered.sort_values("candidate_adjusted_pnl", ascending=True)[columns].head(top_n)


def run_audit(args: argparse.Namespace) -> Path:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = args.output_dir / args.label
    suffix = 0
    while run_dir.exists():
        suffix += 1
        run_dir = args.output_dir / f"{args.label}_{suffix}"
    run_dir.mkdir(parents=True)

    replacement = pd.read_csv(args.replacement_rows)
    side_drift_alerts = read_csv_many(args.side_drift_alerts or [])
    prediction_groups = read_csv_many(args.prediction_group_summaries or [])
    selected_groups = read_csv_many(args.selected_trade_group_summaries or [])
    enriched = enrich_replacement_rows(
        replacement,
        side_drift_alerts=side_drift_alerts,
        prediction_groups=prediction_groups,
        selected_groups=selected_groups,
        recent_month_count=args.recent_month_count,
    )
    conditions = condition_summary(enriched)
    contexts = context_summary(enriched)
    uncovered = top_uncovered_losses(enriched, args.top_n)

    enriched.to_csv(run_dir / "replacement_signal_rows.csv", index=False)
    conditions.to_csv(run_dir / "condition_summary.csv", index=False)
    contexts.to_csv(run_dir / "context_signal_summary.csv", index=False)
    uncovered.to_csv(run_dir / "top_uncovered_losses.csv", index=False)
    metadata = {
        "replacement_rows": args.replacement_rows,
        "side_drift_alerts": args.side_drift_alerts or [],
        "prediction_group_summaries": args.prediction_group_summaries or [],
        "selected_trade_group_summaries": args.selected_trade_group_summaries or [],
        "recent_month_count": args.recent_month_count,
        "top_n": args.top_n,
    }
    (run_dir / "config.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    if conditions.empty:
        print("no replacement signal rows")
    else:
        print(conditions.head(args.print_rows).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replacement-rows", type=Path, required=True)
    parser.add_argument("--side-drift-alerts", type=parse_csv_paths)
    parser.add_argument("--prediction-group-summaries", type=parse_csv_paths)
    parser.add_argument("--selected-trade-group-summaries", type=parse_csv_paths)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="short_budget_replacement_signal_audit")
    parser.add_argument("--recent-month-count", type=int, default=3)
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--print-rows", type=int, default=80)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_audit(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
