#!/usr/bin/env python3
"""Diagnose side-distribution drift from predictions and selected trades."""

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

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


SIDE_NAME_TO_VALUE = {"short": -1, "flat": 0, "long": 1}
SIDE_VALUE_TO_NAME = {-1: "short", 0: "flat", 1: "long"}


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def optional_csv_strings(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def local_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    try:
        return json_default(value)
    except TypeError:
        pass
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def to_side_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        return numeric
    mapped = series.astype("string").str.lower().map(SIDE_NAME_TO_VALUE)
    return pd.to_numeric(mapped, errors="coerce")


def side_name(value: object) -> str:
    if pd.isna(value):
        return "__missing__"
    try:
        return SIDE_VALUE_TO_NAME.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(value)


def value_share(series: pd.Series, value: int) -> float:
    valid = series.dropna()
    if valid.empty:
        return float("nan")
    return float((valid.astype(float) == float(value)).mean())


def boolean_mean(series: pd.Series) -> float:
    valid = series.dropna()
    if valid.empty:
        return float("nan")
    return float(valid.astype(bool).mean())


def side_from_ev(long_score: pd.Series, short_score: pd.Series) -> pd.Series:
    long_values = pd.to_numeric(long_score, errors="coerce")
    short_values = pd.to_numeric(short_score, errors="coerce")
    output = pd.Series(np.nan, index=long_values.index, dtype="float64")
    valid = long_values.notna() & short_values.notna()
    output.loc[valid & (long_values > short_values)] = 1
    output.loc[valid & (short_values > long_values)] = -1
    output.loc[valid & (long_values == short_values)] = 0
    return output


def add_prediction_side_columns(
    predictions: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
) -> pd.DataFrame:
    missing = [column for column in ["decision_timestamp", "dataset_month", long_column, short_column] if column not in predictions.columns]
    if missing:
        raise ValueError(f"predictions missing required columns: {', '.join(missing)}")
    output = predictions.copy()
    output["decision_timestamp"] = pd.to_datetime(output["decision_timestamp"], utc=True)
    output["dataset_month"] = output["dataset_month"].astype(str)
    output["actual_label_side"] = (
        to_side_series(output["label"]) if "label" in output.columns else pd.Series(np.nan, index=output.index)
    )
    output["actual_best_side"] = (
        to_side_series(output["best_side"])
        if "best_side" in output.columns
        else pd.Series(np.nan, index=output.index)
    )
    output["pred_ev_side"] = side_from_ev(output[long_column], output[short_column])
    output["pred_ev_side_name"] = output["pred_ev_side"].map(side_name)
    output["pred_label_side"] = (
        to_side_series(output["pred_label"])
        if "pred_label" in output.columns
        else pd.Series(np.nan, index=output.index)
    )
    output["pred_best_side_side"] = (
        to_side_series(output["pred_best_side"])
        if "pred_best_side" in output.columns
        else pd.Series(np.nan, index=output.index)
    )
    output["pred_side_score"] = pd.to_numeric(output[long_column], errors="coerce") - pd.to_numeric(
        output[short_column], errors="coerce"
    )
    if "side_score" in output.columns:
        output["actual_side_score"] = pd.to_numeric(output["side_score"], errors="coerce")
    else:
        output["actual_side_score"] = np.nan
    best_valid = output["actual_best_side"].notna() & output["pred_ev_side"].notna()
    output["pred_ev_matches_best_side"] = pd.Series(np.nan, index=output.index, dtype="float64")
    output.loc[best_valid, "pred_ev_matches_best_side"] = (
        output.loc[best_valid, "pred_ev_side"].astype(int)
        == output.loc[best_valid, "actual_best_side"].astype(int)
    ).astype(float)
    label_valid = output["actual_label_side"].isin([-1, 1]) & output["pred_ev_side"].notna()
    output["pred_ev_matches_nonflat_label"] = pd.Series(np.nan, index=output.index, dtype="float64")
    output.loc[label_valid, "pred_ev_matches_nonflat_label"] = (
        output.loc[label_valid, "pred_ev_side"].astype(int)
        == output.loc[label_valid, "actual_label_side"].astype(int)
    ).astype(float)
    return output


def summarize_predictions(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    working = frame.copy()
    for column in group_columns:
        if column not in working.columns:
            working[column] = "__missing__"
        working[column] = working[column].astype("string").fillna("__missing__")

    rows: list[dict[str, object]] = []
    for keys, group in working.groupby(group_columns, dropna=False, observed=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row: dict[str, object] = dict(zip(group_columns, keys))
        row.update(
            {
                "prediction_rows": int(len(group)),
                "actual_label_long_share": value_share(group["actual_label_side"], 1),
                "actual_label_short_share": value_share(group["actual_label_side"], -1),
                "actual_label_flat_share": value_share(group["actual_label_side"], 0),
                "actual_best_side_long_share": value_share(group["actual_best_side"], 1),
                "actual_best_side_short_share": value_share(group["actual_best_side"], -1),
                "pred_ev_long_share": value_share(group["pred_ev_side"], 1),
                "pred_ev_short_share": value_share(group["pred_ev_side"], -1),
                "pred_ev_tie_share": value_share(group["pred_ev_side"], 0),
                "pred_label_long_share": value_share(group["pred_label_side"], 1),
                "pred_label_short_share": value_share(group["pred_label_side"], -1),
                "pred_label_flat_share": value_share(group["pred_label_side"], 0),
                "pred_best_side_long_share": value_share(group["pred_best_side_side"], 1),
                "pred_best_side_short_share": value_share(group["pred_best_side_side"], -1),
                "pred_ev_matches_best_side_rate": boolean_mean(group["pred_ev_matches_best_side"]),
                "pred_ev_matches_nonflat_label_rate": boolean_mean(group["pred_ev_matches_nonflat_label"]),
                "actual_side_score_mean": float(pd.to_numeric(group["actual_side_score"], errors="coerce").mean()),
                "pred_side_score_mean": float(pd.to_numeric(group["pred_side_score"], errors="coerce").mean()),
                "pred_short_minus_actual_label_short_share": (
                    value_share(group["pred_ev_side"], -1) - value_share(group["actual_label_side"], -1)
                ),
                "pred_long_minus_actual_label_long_share": (
                    value_share(group["pred_ev_side"], 1) - value_share(group["actual_label_side"], 1)
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_columns).reset_index(drop=True)


def read_selected_trades(
    policy_summary_path: Path,
    *,
    months: list[str],
    variants: list[str],
    cost_cases: list[str],
) -> pd.DataFrame:
    if not policy_summary_path.exists():
        raise FileNotFoundError(f"policy summary not found: {policy_summary_path}")
    summary = pd.read_csv(policy_summary_path)
    required = {"month", "run_dir", "variant", "cost_case"}
    missing = sorted(required - set(summary.columns))
    if missing:
        raise ValueError(f"policy summary missing columns: {', '.join(missing)}")
    summary = summary[summary["month"].astype(str).isin(months)].copy()
    if variants:
        summary = summary[summary["variant"].astype(str).isin(variants)].copy()
    if cost_cases:
        summary = summary[summary["cost_case"].astype(str).isin(cost_cases)].copy()
    frames: list[pd.DataFrame] = []
    for _, row in summary.iterrows():
        trades_path = Path(str(row["run_dir"])) / "trades.csv"
        if not trades_path.exists():
            raise FileNotFoundError(f"trades file not found: {trades_path}")
        trades = pd.read_csv(trades_path)
        if trades.empty:
            continue
        trades = trades.copy()
        trades["month"] = str(row["month"])
        trades["variant"] = str(row["variant"])
        trades["cost_case"] = str(row["cost_case"])
        trades["run_dir"] = str(row["run_dir"])
        frames.append(trades)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def enrich_trades_with_predictions(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    if "entry_decision_timestamp" not in trades.columns:
        raise ValueError("trades missing entry_decision_timestamp")
    lookup_columns = [
        "decision_timestamp",
        "dataset_month",
        "actual_label_side",
        "actual_best_side",
        "pred_ev_side",
        "pred_label_side",
        "pred_best_side_side",
        "pred_side_score",
        "actual_side_score",
        long_column,
        short_column,
    ]
    for optional in [
        "trend_regime",
        "volatility_regime",
        "session_regime",
        "gap_regime",
        "combined_regime",
        "pred_best_side_prob_1",
        "pred_best_side_prob_-1",
    ]:
        if optional in predictions.columns:
            lookup_columns.append(optional)
    lookup = predictions[lookup_columns].drop_duplicates("decision_timestamp").copy()
    output = trades.copy()
    output["entry_decision_timestamp"] = pd.to_datetime(output["entry_decision_timestamp"], utc=True)
    output["direction_side"] = to_side_series(output["direction"])
    output = output.merge(
        lookup,
        left_on="entry_decision_timestamp",
        right_on="decision_timestamp",
        how="left",
        suffixes=("", "_prediction"),
    )
    output["prediction_matched"] = output["decision_timestamp"].notna()
    output["direction_side_name"] = output["direction_side"].map(side_name)
    output["pred_taken_ev"] = np.where(
        output["direction_side"] == 1,
        pd.to_numeric(output[long_column], errors="coerce"),
        pd.to_numeric(output[short_column], errors="coerce"),
    )
    output["pred_opposite_ev"] = np.where(
        output["direction_side"] == 1,
        pd.to_numeric(output[short_column], errors="coerce"),
        pd.to_numeric(output[long_column], errors="coerce"),
    )
    output["ev_overestimate_vs_realized"] = output["pred_taken_ev"] - pd.to_numeric(
        output["adjusted_pnl"], errors="coerce"
    )
    best_valid = output["actual_best_side"].notna() & output["direction_side"].notna()
    output["direction_error"] = pd.Series(np.nan, index=output.index, dtype="float64")
    output.loc[best_valid, "direction_error"] = (
        output.loc[best_valid, "direction_side"].astype(int)
        != output.loc[best_valid, "actual_best_side"].astype(int)
    ).astype(float)
    label_valid = output["actual_label_side"].isin([-1, 1]) & output["direction_side"].notna()
    output["label_direction_error"] = pd.Series(np.nan, index=output.index, dtype="float64")
    output.loc[label_valid, "label_direction_error"] = (
        output.loc[label_valid, "direction_side"].astype(int)
        != output.loc[label_valid, "actual_label_side"].astype(int)
    ).astype(float)
    output["no_edge_label"] = output["actual_label_side"] == 0
    pred_valid = output["pred_ev_side"].notna() & output["direction_side"].notna()
    output["pred_ev_matches_trade"] = pd.Series(np.nan, index=output.index, dtype="float64")
    output.loc[pred_valid, "pred_ev_matches_trade"] = (
        output.loc[pred_valid, "pred_ev_side"].astype(int)
        == output.loc[pred_valid, "direction_side"].astype(int)
    ).astype(float)
    return output


def summarize_selected_month(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for keys, group in frame.groupby(["cost_case", "variant", "month"], dropna=False, observed=True):
        cost_case, variant, month = keys
        direction = group["direction_side"]
        adjusted = pd.to_numeric(group["adjusted_pnl"], errors="coerce")
        row = {
            "cost_case": cost_case,
            "variant": variant,
            "month": month,
            "trade_count": int(len(group)),
            "matched_prediction_rate": float(group["prediction_matched"].mean()),
            "total_adjusted_pnl": float(adjusted.sum()),
            "avg_adjusted_pnl": float(adjusted.mean()),
            "win_rate": float((adjusted > 0).mean()),
            "long_trade_count": int((direction == 1).sum()),
            "short_trade_count": int((direction == -1).sum()),
            "long_trade_share": float((direction == 1).mean()),
            "short_trade_share": float((direction == -1).mean()),
            "long_adjusted_pnl": float(adjusted[direction == 1].sum()),
            "short_adjusted_pnl": float(adjusted[direction == -1].sum()),
            "direction_error_rate": boolean_mean(group["direction_error"]),
            "label_direction_error_rate": boolean_mean(group["label_direction_error"]),
            "no_edge_rate": boolean_mean(group["no_edge_label"]),
            "pred_ev_matches_trade_rate": boolean_mean(group["pred_ev_matches_trade"]),
            "ev_overestimate_vs_realized_mean": float(group["ev_overestimate_vs_realized"].mean()),
            "selected_actual_label_long_share": value_share(group["actual_label_side"], 1),
            "selected_actual_label_short_share": value_share(group["actual_label_side"], -1),
            "selected_actual_label_flat_share": value_share(group["actual_label_side"], 0),
            "selected_pred_ev_long_share": value_share(group["pred_ev_side"], 1),
            "selected_pred_ev_short_share": value_share(group["pred_ev_side"], -1),
        }
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["cost_case", "variant", "month"]).reset_index(drop=True)


def summarize_selected_by_side(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    working = frame.copy()
    for column in group_columns:
        if column not in working.columns:
            working[column] = "__missing__"
        working[column] = working[column].astype("string").fillna("__missing__")
    working["direction_side_name"] = working["direction_side"].map(side_name)
    all_group_columns = ["cost_case", "variant", *group_columns, "direction_side_name"]
    rows: list[dict[str, object]] = []
    for keys, group in working.groupby(all_group_columns, dropna=False, observed=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        adjusted = pd.to_numeric(group["adjusted_pnl"], errors="coerce")
        row: dict[str, object] = dict(zip(all_group_columns, keys))
        row.update(
            {
                "trade_count": int(len(group)),
                "total_adjusted_pnl": float(adjusted.sum()),
                "avg_adjusted_pnl": float(adjusted.mean()),
                "win_rate": float((adjusted > 0).mean()),
                "direction_error_rate": boolean_mean(group["direction_error"]),
                "label_direction_error_rate": boolean_mean(group["label_direction_error"]),
                "no_edge_rate": boolean_mean(group["no_edge_label"]),
                "pred_ev_matches_trade_rate": boolean_mean(group["pred_ev_matches_trade"]),
                "ev_overestimate_vs_realized_mean": float(group["ev_overestimate_vs_realized"].mean()),
                "pred_taken_ev_mean": float(group["pred_taken_ev"].mean()),
                "pred_opposite_ev_mean": float(group["pred_opposite_ev"].mean()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["cost_case", "variant", *group_columns, "direction_side_name"]
    ).reset_index(drop=True)


def build_side_drift_alerts(
    prediction_group_summary: pd.DataFrame,
    selected_side_summary: pd.DataFrame,
    *,
    group_columns: list[str],
    min_alert_trades: int,
    min_alert_bias: float,
) -> pd.DataFrame:
    if prediction_group_summary.empty or selected_side_summary.empty:
        return pd.DataFrame()
    prediction = prediction_group_summary.copy()
    if "dataset_month" in prediction.columns:
        prediction = prediction.rename(columns={"dataset_month": "month"})
    key_columns = ["month", *group_columns]
    rows: list[pd.DataFrame] = []
    for side in ["long", "short"]:
        side_value = SIDE_NAME_TO_VALUE[side]
        pred_share_col = f"pred_ev_{side}_share"
        actual_share_col = f"actual_label_{side}_share"
        side_prediction = prediction[key_columns + ["prediction_rows", pred_share_col, actual_share_col]].copy()
        side_prediction["side"] = side
        side_prediction["pred_ev_side_share"] = side_prediction[pred_share_col]
        side_prediction["actual_label_side_share"] = side_prediction[actual_share_col]
        side_prediction["side_share_bias"] = (
            side_prediction["pred_ev_side_share"] - side_prediction["actual_label_side_share"]
        )
        side_prediction = side_prediction.drop(columns=[pred_share_col, actual_share_col])
        side_trades = selected_side_summary[
            selected_side_summary["direction_side_name"].astype(str).eq(side)
        ].copy()
        if side_trades.empty:
            continue
        merged = side_prediction.merge(
            side_trades,
            on=key_columns,
            how="inner",
        )
        merged["side_value"] = side_value
        rows.append(merged)
    if not rows:
        return pd.DataFrame()
    output = pd.concat(rows, ignore_index=True, sort=False)
    output["loss_bias_score"] = output["side_share_bias"].clip(lower=0) * (
        -output["total_adjusted_pnl"].clip(upper=0)
    )
    output["is_alert"] = (
        (output["trade_count"] >= min_alert_trades)
        & (output["side_share_bias"] >= min_alert_bias)
        & (output["total_adjusted_pnl"] < 0)
    )
    sort_columns = ["is_alert", "loss_bias_score", "total_adjusted_pnl", "trade_count"]
    return output.sort_values(sort_columns, ascending=[False, False, True, False]).reset_index(drop=True)


def run_diagnostics(
    *,
    predictions_path: Path,
    policy_summary_path: Path | None,
    months: list[str],
    variants: list[str],
    cost_cases: list[str],
    group_columns: list[str],
    long_column: str,
    short_column: str,
    output_dir: Path,
    min_alert_trades: int,
    min_alert_bias: float,
) -> dict[str, object]:
    raw_predictions = pd.read_parquet(predictions_path)
    predictions = add_prediction_side_columns(
        raw_predictions,
        long_column=long_column,
        short_column=short_column,
    )
    predictions = predictions[predictions["dataset_month"].astype(str).isin(months)].copy()
    prediction_month = summarize_predictions(predictions, ["dataset_month"])
    prediction_group = summarize_predictions(predictions, ["dataset_month", *group_columns])

    selected_month = pd.DataFrame()
    selected_group = pd.DataFrame()
    alerts = pd.DataFrame()
    enriched_trades = pd.DataFrame()
    if policy_summary_path is not None:
        trades = read_selected_trades(
            policy_summary_path,
            months=months,
            variants=variants,
            cost_cases=cost_cases,
        )
        enriched_trades = enrich_trades_with_predictions(
            trades,
            predictions,
            long_column=long_column,
            short_column=short_column,
        )
        selected_month = summarize_selected_month(enriched_trades)
        selected_group = summarize_selected_by_side(enriched_trades, ["month", *group_columns])
        alerts = build_side_drift_alerts(
            prediction_group,
            selected_group,
            group_columns=group_columns,
            min_alert_trades=min_alert_trades,
            min_alert_bias=min_alert_bias,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_month.to_csv(output_dir / "prediction_month_summary.csv", index=False)
    prediction_group.to_csv(output_dir / "prediction_group_summary.csv", index=False)
    if not selected_month.empty:
        selected_month.to_csv(output_dir / "selected_trade_month_summary.csv", index=False)
    if not selected_group.empty:
        selected_group.to_csv(output_dir / "selected_trade_group_summary.csv", index=False)
    if not alerts.empty:
        alerts.to_csv(output_dir / "side_drift_alerts.csv", index=False)
    if not enriched_trades.empty:
        enriched_trades.to_csv(output_dir / "enriched_selected_trades.csv", index=False)

    metrics: dict[str, object] = {
        "mode": "side_drift_diagnostics",
        "predictions": str(predictions_path),
        "policy_summary": str(policy_summary_path) if policy_summary_path is not None else "",
        "months": months,
        "variants": variants,
        "cost_cases": cost_cases,
        "group_columns": group_columns,
        "long_column": long_column,
        "short_column": short_column,
        "rows": {
            "predictions": int(len(predictions)),
            "selected_trades": int(len(enriched_trades)),
            "prediction_month_groups": int(len(prediction_month)),
            "prediction_regime_groups": int(len(prediction_group)),
            "alerts": int(len(alerts)),
            "active_alerts": int(alerts["is_alert"].sum()) if "is_alert" in alerts.columns else 0,
        },
        "outputs": {
            "prediction_month_summary": str(output_dir / "prediction_month_summary.csv"),
            "prediction_group_summary": str(output_dir / "prediction_group_summary.csv"),
            "selected_trade_month_summary": str(output_dir / "selected_trade_month_summary.csv"),
            "selected_trade_group_summary": str(output_dir / "selected_trade_group_summary.csv"),
            "side_drift_alerts": str(output_dir / "side_drift_alerts.csv"),
            "enriched_selected_trades": str(output_dir / "enriched_selected_trades.csv"),
        },
    }
    if not alerts.empty:
        top = alerts.head(10).copy()
        metrics["top_alerts"] = top.to_dict(orient="records")
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--policy-summary", type=Path, default=None)
    parser.add_argument("--months", type=parse_csv_strings, required=True)
    parser.add_argument("--variants", type=optional_csv_strings, default=[])
    parser.add_argument("--cost-cases", type=optional_csv_strings, default=[])
    parser.add_argument(
        "--group-columns",
        type=optional_csv_strings,
        default=["combined_regime", "session_regime"],
    )
    parser.add_argument("--long-column", default="pred_long_best_adjusted_pnl")
    parser.add_argument("--short-column", default="pred_short_best_adjusted_pnl")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/modeling"))
    parser.add_argument("--label", default="side_drift_diagnostics")
    parser.add_argument("--min-alert-trades", type=int, default=3)
    parser.add_argument("--min-alert-bias", type=float, default=0.10)
    args = parser.parse_args(argv)

    output_dir = make_run_dir(args.output_dir, args.label)
    metrics = run_diagnostics(
        predictions_path=args.predictions,
        policy_summary_path=args.policy_summary,
        months=args.months,
        variants=args.variants,
        cost_cases=args.cost_cases,
        group_columns=args.group_columns,
        long_column=args.long_column,
        short_column=args.short_column,
        output_dir=output_dir,
        min_alert_trades=args.min_alert_trades,
        min_alert_bias=args.min_alert_bias,
    )
    print(f"artifacts: {output_dir}")
    print(json.dumps(metrics["rows"], indent=2, default=local_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
