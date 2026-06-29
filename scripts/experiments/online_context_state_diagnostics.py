#!/usr/bin/env python3
"""Diagnose online context state available before each executed trade."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import (  # noqa: E402
    ModelPolicyConfig,
    attach_trade_prediction_columns,
    json_default,
    make_run_dir,
    model_policy_entry_margin,
    parse_csv_floats,
    parse_csv_paths,
    parse_csv_string_tuple,
)


MODEL_POLICY_TUPLE_FIELDS = {
    "fixed_horizon_minutes",
    "long_fixed_horizon_columns",
    "short_fixed_horizon_columns",
    "side_confidence_penalty_rules",
    "side_confidence_overfit_penalty_rules",
    "side_ev_penalty_rules",
    "extra_side_margin_rules",
    "side_extra_margin_rules",
    "side_block_rules",
    "context_drawdown_guard_context_columns",
    "block_trend_regimes",
    "block_volatility_regimes",
    "block_session_regimes",
    "block_gap_regimes",
    "block_combined_regimes",
}

DEFAULT_CONTEXT_COLUMNS = ("dataset_month",)
DEFAULT_EXTRA_PREDICTION_COLUMNS = (
    "dataset_month",
    "combined_regime",
    "session_regime",
    "pred_long_best_adjusted_pnl",
    "pred_short_best_adjusted_pnl",
    "pred_best_side_prob_1",
    "pred_best_side_prob_-1",
    "pred_long_profit_barrier_hit",
    "pred_short_profit_barrier_hit",
)


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


def expand_run_paths(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if (path / "config.json").exists() and (path / "trades.csv").exists():
            expanded.append(path)
            continue
        if not path.is_dir():
            raise FileNotFoundError(f"run path not found: {path}")
        children = sorted(
            child
            for child in path.iterdir()
            if (child / "config.json").exists() and (child / "trades.csv").exists()
        )
        if not children:
            raise FileNotFoundError(f"no trade run dirs under: {path}")
        expanded.extend(children)
    return expanded


def restore_model_policy_config(config: dict[str, Any]) -> ModelPolicyConfig:
    defaults = {
        field.name: getattr(ModelPolicyConfig(predictions=Path("")), field.name)
        for field in fields(ModelPolicyConfig)
    }
    values: dict[str, Any] = {}
    for name, default in defaults.items():
        value = config.get(name, default)
        if name == "predictions":
            value = Path(value)
        elif name in MODEL_POLICY_TUPLE_FIELDS:
            value = tuple(value)
        values[name] = value
    return ModelPolicyConfig(**values)


def read_run_config(path: Path) -> dict[str, Any]:
    with (path / "config.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def direction_code(direction: str) -> int:
    normalized = str(direction).strip().lower()
    if normalized == "long":
        return 1
    if normalized == "short":
        return -1
    return 0


def direction_label(code: int) -> str:
    if code > 0:
        return "long"
    if code < 0:
        return "short"
    return "flat"


def format_context(row: pd.Series, context_columns: tuple[str, ...]) -> str:
    if not context_columns:
        return "__all__"
    parts: list[str] = []
    for column in context_columns:
        value = row[column] if column in row else "__missing__"
        if pd.isna(value):
            value = "__missing__"
        parts.append(f"{column}={value}")
    return "|".join(parts)


def context_key(
    *,
    month: str,
    direction: str,
    context_value: str,
    reset_monthly: bool,
) -> str:
    if reset_monthly:
        return f"{month}|{direction}|{context_value}"
    return f"{direction}|{context_value}"


def minutes_between(later: pd.Timestamp | None, earlier: pd.Timestamp | None) -> float:
    if later is None or earlier is None or pd.isna(later) or pd.isna(earlier):
        return float("nan")
    return float((later - earlier) / pd.Timedelta(minutes=1))


def initial_state(thresholds: tuple[float, ...]) -> dict[str, Any]:
    return {
        "pnl": 0.0,
        "trade_count": 0,
        "win_count": 0,
        "loss_count": 0,
        "last_exit_decision_timestamp": pd.NaT,
        "last_exit_timestamp": pd.NaT,
        "breached_at": {threshold: pd.NaT for threshold in thresholds},
    }


def add_bucket_columns(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["prior_context_pnl_bucket"] = pd.cut(
        output["prior_context_pnl"].astype(float),
        bins=[-np.inf, -120, -60, -20, 0, 60, np.inf],
        labels=["<=-120", "-120..-60", "-60..-20", "-20..0", "0..60", ">60"],
        right=False,
    ).astype("string")
    output["prior_context_trade_count_bucket"] = pd.cut(
        output["prior_context_trade_count"].astype(float),
        bins=[-0.5, 0.5, 1.5, 3.5, np.inf],
        labels=["0", "1", "2-3", "4+"],
        right=True,
    ).astype("string")
    output["entry_margin_bucket"] = pd.cut(
        output["entry_margin"].astype(float),
        bins=[-np.inf, 0, 5, 10, 20, np.inf],
        labels=["<=0", "0..5", "5..10", "10..20", ">20"],
        right=False,
    ).astype("string")
    if "minutes_since_context_breach_20" in output.columns:
        output["minutes_since_breach20_bucket"] = pd.cut(
            output["minutes_since_context_breach_20"].astype(float),
            bins=[-np.inf, 60, 360, 1440, np.inf],
            labels=["<=60", "60..360", "360..1440", ">1440"],
            right=False,
        ).astype("string")
        output.loc[
            output["minutes_since_context_breach_20"].isna(),
            "minutes_since_breach20_bucket",
        ] = "none"
    return output


def annotate_online_context_state(
    trades: pd.DataFrame,
    *,
    context_columns: tuple[str, ...] = DEFAULT_CONTEXT_COLUMNS,
    thresholds: tuple[float, ...] = (20.0, 40.0, 60.0),
    reset_monthly: bool = True,
) -> pd.DataFrame:
    required = {
        "direction",
        "entry_timestamp",
        "exit_timestamp",
        "entry_decision_timestamp",
        "exit_decision_timestamp",
        "adjusted_pnl",
    }
    missing = sorted(required - set(trades.columns))
    if missing:
        raise ValueError(f"trades missing columns: {', '.join(missing)}")
    missing_context = sorted(set(context_columns) - set(trades.columns))
    if missing_context:
        raise ValueError(f"trades missing context columns: {', '.join(missing_context)}")

    output = trades.copy()
    for column in [
        "entry_timestamp",
        "exit_timestamp",
        "entry_decision_timestamp",
        "exit_decision_timestamp",
    ]:
        output[column] = pd.to_datetime(output[column], utc=True)
    output["adjusted_pnl"] = pd.to_numeric(output["adjusted_pnl"], errors="raise")
    output["entry_month"] = output["entry_timestamp"].dt.strftime("%Y-%m")
    output["direction"] = output["direction"].astype("string")
    output["online_context"] = output.apply(
        lambda row: format_context(row, context_columns),
        axis=1,
    )
    output["online_context_key"] = output.apply(
        lambda row: context_key(
            month=str(row["entry_month"]),
            direction=str(row["direction"]),
            context_value=str(row["online_context"]),
            reset_monthly=reset_monthly,
        ),
        axis=1,
    )
    output["online_side_month_key"] = output.apply(
        lambda row: context_key(
            month=str(row["entry_month"]),
            direction=str(row["direction"]),
            context_value="__side_month__",
            reset_monthly=True,
        ),
        axis=1,
    )

    thresholds = tuple(sorted(float(value) for value in thresholds if np.isfinite(value)))
    context_states: dict[str, dict[str, Any]] = {}
    side_month_states: dict[str, dict[str, Any]] = {}
    all_rows: list[dict[str, Any]] = []

    ordered = output.sort_values(["entry_decision_timestamp", "entry_timestamp"]).reset_index()
    for _, row in ordered.iterrows():
        context_state = context_states.setdefault(
            str(row["online_context_key"]),
            initial_state(thresholds),
        )
        side_state = side_month_states.setdefault(
            str(row["online_side_month_key"]),
            initial_state(thresholds),
        )
        entry_decision_timestamp = row["entry_decision_timestamp"]
        state_row: dict[str, Any] = {
            "index": int(row["index"]),
            "prior_context_pnl": float(context_state["pnl"]),
            "prior_context_trade_count": int(context_state["trade_count"]),
            "prior_context_win_rate": (
                np.nan
                if context_state["trade_count"] == 0
                else context_state["win_count"] / context_state["trade_count"]
            ),
            "prior_side_month_pnl": float(side_state["pnl"]),
            "prior_side_month_trade_count": int(side_state["trade_count"]),
            "minutes_since_context_last_exit": minutes_between(
                entry_decision_timestamp,
                context_state["last_exit_decision_timestamp"],
            ),
        }
        for threshold in thresholds:
            threshold_label = f"{threshold:g}"
            breached_at = context_state["breached_at"][threshold]
            side_breached_at = side_state["breached_at"][threshold]
            state_row[f"prior_context_active_loss_breach_{threshold_label}"] = bool(
                context_state["pnl"] <= -threshold
            )
            state_row[f"prior_context_ever_breached_{threshold_label}"] = bool(
                pd.notna(breached_at)
            )
            state_row[f"minutes_since_context_breach_{threshold_label}"] = minutes_between(
                entry_decision_timestamp,
                breached_at,
            )
            state_row[f"prior_side_month_active_loss_breach_{threshold_label}"] = bool(
                side_state["pnl"] <= -threshold
            )
            state_row[f"prior_side_month_ever_breached_{threshold_label}"] = bool(
                pd.notna(side_breached_at)
            )
        all_rows.append(state_row)

        adjusted_pnl = float(row["adjusted_pnl"])
        for state in (context_state, side_state):
            state["pnl"] += adjusted_pnl
            state["trade_count"] += 1
            if adjusted_pnl > 0:
                state["win_count"] += 1
            else:
                state["loss_count"] += 1
            state["last_exit_decision_timestamp"] = row["exit_decision_timestamp"]
            state["last_exit_timestamp"] = row["exit_timestamp"]
            for threshold in thresholds:
                if state["pnl"] <= -threshold and pd.isna(state["breached_at"][threshold]):
                    state["breached_at"][threshold] = row["exit_decision_timestamp"]

    state_frame = pd.DataFrame(all_rows).set_index("index").sort_index()
    annotated = pd.concat([output, state_frame], axis=1)
    return add_bucket_columns(annotated)


def aggregate_summary(
    frame: pd.DataFrame,
    group_columns: list[str],
    *,
    large_loss_threshold: float,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    missing = sorted(set(group_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"summary missing group columns: {', '.join(missing)}")
    grouped = (
        frame.groupby(group_columns, dropna=False)
        .agg(
            trade_count=("adjusted_pnl", "size"),
            total_adjusted_pnl=("adjusted_pnl", "sum"),
            avg_adjusted_pnl=("adjusted_pnl", "mean"),
            win_rate=("adjusted_pnl", lambda values: float((values > 0).mean())),
            large_loss_rate=(
                "adjusted_pnl",
                lambda values: float((values <= large_loss_threshold).mean()),
            ),
            worst_trade_pnl=("adjusted_pnl", "min"),
            prior_context_pnl_mean=("prior_context_pnl", "mean"),
            entry_margin_mean=("entry_margin", "mean"),
        )
        .reset_index()
    )
    return grouped.sort_values(["total_adjusted_pnl", "trade_count"], ascending=[True, False])


def threshold_reentry_summary(
    frame: pd.DataFrame,
    *,
    thresholds: tuple[float, ...],
    large_loss_threshold: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        label = f"{threshold:g}"
        for mode, column in [
            ("ever_breached", f"prior_context_ever_breached_{label}"),
            ("active_loss_breach", f"prior_context_active_loss_breach_{label}"),
        ]:
            subset = frame[frame[column].astype(bool)]
            if subset.empty:
                rows.append(
                    {
                        "threshold": threshold,
                        "mode": mode,
                        "trade_count": 0,
                        "total_adjusted_pnl": 0.0,
                        "avg_adjusted_pnl": np.nan,
                        "win_rate": np.nan,
                        "large_loss_rate": np.nan,
                        "short_adjusted_pnl": 0.0,
                        "long_adjusted_pnl": 0.0,
                    }
                )
                continue
            short_pnl = subset.loc[subset["direction"].eq("short"), "adjusted_pnl"].sum()
            long_pnl = subset.loc[subset["direction"].eq("long"), "adjusted_pnl"].sum()
            rows.append(
                {
                    "threshold": threshold,
                    "mode": mode,
                    "trade_count": int(len(subset)),
                    "total_adjusted_pnl": float(subset["adjusted_pnl"].sum()),
                    "avg_adjusted_pnl": float(subset["adjusted_pnl"].mean()),
                    "win_rate": float((subset["adjusted_pnl"] > 0).mean()),
                    "large_loss_rate": float(
                        (subset["adjusted_pnl"] <= large_loss_threshold).mean()
                    ),
                    "short_adjusted_pnl": float(short_pnl),
                    "long_adjusted_pnl": float(long_pnl),
                }
            )
    return pd.DataFrame(rows)


def load_prediction_frame(
    predictions_path: Path,
    config: ModelPolicyConfig,
    *,
    context_columns: tuple[str, ...],
) -> pd.DataFrame:
    predictions = pd.read_parquet(predictions_path).copy()
    predictions["decision_timestamp"] = pd.to_datetime(
        predictions["decision_timestamp"],
        utc=True,
    )
    timestamp_frame = pd.DataFrame({"timestamp": predictions["decision_timestamp"]})
    predictions["entry_margin"] = model_policy_entry_margin(timestamp_frame, predictions, config)
    needed = {
        "decision_timestamp",
        "entry_margin",
        *context_columns,
        *DEFAULT_EXTRA_PREDICTION_COLUMNS,
        config.long_column,
        config.short_column,
    }
    selected = [column for column in needed if column in predictions.columns]
    return predictions[selected].copy()


def read_and_enrich_runs(
    run_paths: list[Path],
    *,
    context_columns: tuple[str, ...],
) -> pd.DataFrame:
    prediction_cache: dict[Path, pd.DataFrame] = {}
    rows: list[pd.DataFrame] = []
    for run_path in run_paths:
        config_json = read_run_config(run_path)
        policy_config = restore_model_policy_config(config_json["model_policy_config"])
        predictions_path = policy_config.predictions
        if predictions_path not in prediction_cache:
            prediction_cache[predictions_path] = load_prediction_frame(
                predictions_path,
                policy_config,
                context_columns=context_columns,
            )
        predictions = prediction_cache[predictions_path]
        trades = pd.read_csv(run_path / "trades.csv")
        if trades.empty:
            continue
        enriched = attach_trade_prediction_columns(
            trades,
            predictions,
            [
                "entry_margin",
                *context_columns,
                *DEFAULT_EXTRA_PREDICTION_COLUMNS,
                policy_config.long_column,
                policy_config.short_column,
            ],
        )
        enriched["source_run"] = str(run_path)
        enriched["run_month"] = pd.Timestamp(
            config_json["backtest_config"]["evaluation_start"]
        ).strftime("%Y-%m")
        if policy_config.long_column in enriched.columns and policy_config.short_column in enriched.columns:
            long_score = pd.to_numeric(enriched[policy_config.long_column], errors="coerce")
            short_score = pd.to_numeric(enriched[policy_config.short_column], errors="coerce")
            direction = enriched["direction"].map(direction_code)
            enriched["pred_taken_score"] = np.where(direction > 0, long_score, short_score)
            enriched["pred_opposite_score"] = np.where(direction > 0, short_score, long_score)
            enriched["pred_taken_score_gap"] = (
                enriched["pred_taken_score"] - enriched["pred_opposite_score"]
            )
        rows.append(enriched)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def run_diagnostics(
    *,
    run_paths: list[Path],
    output_dir: Path,
    label: str,
    context_columns: tuple[str, ...],
    thresholds: tuple[float, ...],
    reset_monthly: bool,
    large_loss_threshold: float,
) -> Path:
    run_dir = make_run_dir(output_dir, label)
    trades = read_and_enrich_runs(run_paths, context_columns=context_columns)
    annotated = annotate_online_context_state(
        trades,
        context_columns=context_columns,
        thresholds=thresholds,
        reset_monthly=reset_monthly,
    )
    annotated.to_csv(run_dir / "enriched_context_state_trades.csv", index=False)

    threshold_summary = threshold_reentry_summary(
        annotated,
        thresholds=thresholds,
        large_loss_threshold=large_loss_threshold,
    )
    threshold_summary.to_csv(run_dir / "summary_by_threshold.csv", index=False)

    for name, columns in {
        "threshold_direction": ["direction"],
        "prior_context_pnl_bucket": ["prior_context_pnl_bucket"],
        "prior_context_trade_count_bucket": ["prior_context_trade_count_bucket"],
        "entry_margin_bucket": ["entry_margin_bucket"],
        "context": ["direction", *list(context_columns)],
        "regime_session": ["direction", "combined_regime", "session_regime"],
    }.items():
        summary = aggregate_summary(
            annotated,
            columns,
            large_loss_threshold=large_loss_threshold,
        )
        summary.to_csv(run_dir / f"summary_by_{name}.csv", index=False)

    breach_summaries: list[pd.DataFrame] = []
    for threshold in thresholds:
        label_value = f"{threshold:g}"
        column = f"prior_context_ever_breached_{label_value}"
        breached = annotated[annotated[column].astype(bool)].copy()
        if breached.empty:
            continue
        for name, columns in {
            "direction": ["direction"],
            "entry_margin_bucket": ["entry_margin_bucket"],
            "minutes_since_breach": ["minutes_since_breach20_bucket"]
            if threshold == 20.0 and "minutes_since_breach20_bucket" in breached.columns
            else [],
            "regime_session": ["direction", "combined_regime", "session_regime"],
        }.items():
            if not columns:
                continue
            summary = aggregate_summary(
                breached,
                columns,
                large_loss_threshold=large_loss_threshold,
            )
            summary.insert(0, "threshold", threshold)
            summary.insert(1, "breach_group", name)
            breach_summaries.append(summary)
            summary.to_csv(
                run_dir / f"breached_threshold_{label_value}_by_{name}.csv",
                index=False,
            )
    if breach_summaries:
        pd.concat(breach_summaries, ignore_index=True).to_csv(
            run_dir / "breached_group_summaries.csv",
            index=False,
        )

    metrics = {
        "runs": [str(path) for path in run_paths],
        "row_count": int(len(annotated)),
        "total_adjusted_pnl": float(annotated["adjusted_pnl"].sum()),
        "context_columns": context_columns,
        "thresholds": thresholds,
        "reset_monthly": reset_monthly,
        "large_loss_threshold": large_loss_threshold,
    }
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "runs": [str(path) for path in run_paths],
                "output_dir": output_dir,
                "label": label,
                "context_columns": context_columns,
                "thresholds": thresholds,
                "reset_monthly": reset_monthly,
                "large_loss_threshold": large_loss_threshold,
            },
            ensure_ascii=False,
            indent=2,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )
    print(threshold_summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose prior online context state before executed trades.",
    )
    parser.add_argument("--runs", type=parse_csv_paths, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="online_context_state_diagnostics")
    parser.add_argument(
        "--context-columns",
        default="dataset_month",
        help="comma-separated prediction columns used with direction as context",
    )
    parser.add_argument(
        "--thresholds",
        default="20,40,60",
        help="comma-separated realized context loss thresholds to diagnose",
    )
    parser.add_argument(
        "--reset-monthly",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--large-loss-threshold", type=float, default=-15.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_diagnostics(
        run_paths=expand_run_paths(args.runs),
        output_dir=args.output_dir,
        label=args.label,
        context_columns=parse_csv_string_tuple(args.context_columns),
        thresholds=tuple(parse_csv_floats(args.thresholds)),
        reset_monthly=args.reset_monthly,
        large_loss_threshold=args.large_loss_threshold,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
