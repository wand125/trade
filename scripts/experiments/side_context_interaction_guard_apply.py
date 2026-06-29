#!/usr/bin/env python3
"""Apply context drawdown only inside side-drift guarded prediction contexts."""

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
    BacktestConfig,
    ModelPolicyConfig,
    equity_curve,
    json_default,
    make_run_dir,
    model_policy_entry_margin,
    model_signal_from_predictions,
    parse_csv_floats,
    parse_csv_paths,
    parse_csv_string_tuple,
    parsed_side_ev_penalty_rules,
    read_ohlcv,
    read_prediction_frame,
    run_backtest,
    side_rule_condition_mask,
    slice_for_month,
    summarize_trades,
    trades_to_frame,
    write_result,
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


def parse_csv_bools(value: str) -> list[bool]:
    values: list[bool] = []
    for part in [part.strip().lower() for part in value.split(",") if part.strip()]:
        if part in {"1", "true", "yes", "y"}:
            values.append(True)
        elif part in {"0", "false", "no", "n"}:
            values.append(False)
        else:
            raise argparse.ArgumentTypeError("boolean values must be true/false")
    if not values:
        raise argparse.ArgumentTypeError("at least one boolean value is required")
    return values


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


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
            raise FileNotFoundError(f"no model-policy run dirs under: {path}")
        expanded.extend(children)
    return expanded


def load_run_config(path: Path) -> dict[str, Any]:
    return json.loads((path / "config.json").read_text(encoding="utf-8"))


def restore_backtest_config(config: dict[str, Any]) -> BacktestConfig:
    return BacktestConfig(
        evaluation_start=pd.Timestamp(config["evaluation_start"]),
        evaluation_end=pd.Timestamp(config["evaluation_end"]),
        max_holding=pd.Timedelta(config.get("max_holding", "1 days 00:00:00")),
        profit_multiplier=float(config.get("profit_multiplier", 1.0)),
        loss_multiplier=float(config.get("loss_multiplier", 1.2)),
        spread_points=float(config.get("spread_points", 0.0)),
        slippage_points=float(config.get("slippage_points", 0.0)),
        execution_delay_bars=int(config.get("execution_delay_bars", 0)),
    )


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


def threshold_label(value: float) -> str:
    if value == float("inf"):
        return "inf"
    if value == -float("inf"):
        return "minf"
    return str(value).replace("-", "m").replace(".", "p")


def base_context_series(
    df: pd.DataFrame,
    predictions: pd.DataFrame,
    context_columns: tuple[str, ...],
) -> pd.Series:
    if not context_columns:
        return pd.Series("__all__", index=df.index, dtype="string")
    prediction_index = predictions.set_index("decision_timestamp")
    missing = sorted(set(context_columns) - set(prediction_index.columns))
    if missing:
        raise ValueError(
            "interaction context missing prediction columns: " + ", ".join(missing)
        )
    aligned = prediction_index[list(context_columns)].reindex(df["timestamp"]).reset_index(drop=True)
    parts: list[pd.Series] = []
    for column in context_columns:
        values = aligned[column].astype("string").fillna("__missing__")
        parts.append(column + "=" + values)
    output = parts[0]
    for part in parts[1:]:
        output = output + "|" + part
    return pd.Series(output.to_numpy(), index=df.index, dtype="string")


def side_rule_match_mask(
    df: pd.DataFrame,
    predictions: pd.DataFrame,
    policy_config: ModelPolicyConfig,
    signal: pd.Series,
    *,
    match_mode: str,
    short_gap_threshold: float = 0.0,
) -> pd.Series:
    if match_mode not in {"any_rule", "selected_side_rule", "signal_short_raw_gap"}:
        raise ValueError(
            "match_mode must be any_rule, selected_side_rule, or signal_short_raw_gap"
        )
    if match_mode == "signal_short_raw_gap":
        prediction_index = predictions.set_index("decision_timestamp")
        aligned = prediction_index[
            [policy_config.long_column, policy_config.short_column]
        ].reindex(df["timestamp"])
        long_score = aligned[policy_config.long_column].reset_index(drop=True).astype(float)
        short_score = aligned[policy_config.short_column].reset_index(drop=True).astype(float)
        raw_short_gap = short_score - long_score
        return (
            signal.eq(-1)
            & raw_short_gap.notna()
            & np.isfinite(raw_short_gap)
            & raw_short_gap.ge(short_gap_threshold)
        ).fillna(False).astype(bool)
    prediction_index = predictions.set_index("decision_timestamp")
    active = pd.Series(False, index=df.index)
    for side, conditions, _ in parsed_side_ev_penalty_rules(policy_config):
        mask = side_rule_condition_mask(
            prediction_index,
            df["timestamp"],
            df.index,
            conditions,
        )
        if match_mode == "selected_side_rule":
            mask &= signal.eq(side)
        active |= mask
    return active.fillna(False).astype(bool)


def interaction_entry_context(
    df: pd.DataFrame,
    predictions: pd.DataFrame,
    policy_config: ModelPolicyConfig,
    signal: pd.Series,
    *,
    context_columns: tuple[str, ...],
    match_mode: str,
    short_gap_threshold: float = 0.0,
) -> tuple[pd.Series, pd.Series]:
    active = side_rule_match_mask(
        df,
        predictions,
        policy_config,
        signal,
        match_mode=match_mode,
        short_gap_threshold=short_gap_threshold,
    )
    base_context = base_context_series(df, predictions, context_columns)
    timestamps = pd.to_datetime(df["timestamp"], utc=True).dt.strftime("%Y%m%d%H%M%S")
    inactive_context = pd.Series(
        "inactive|row=" + pd.Series(np.arange(len(df)), index=df.index).astype(str)
        + "|ts="
        + timestamps.astype(str),
        index=df.index,
        dtype="string",
    )
    active_context = pd.Series(
        "guarded|" + base_context.astype("string"),
        index=df.index,
        dtype="string",
    )
    context = active_context.where(active, inactive_context)
    return context.astype("string"), active


def aggregate_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    return (
        summary.groupby(
            [
                "match_mode",
                "context_drawdown_guard_loss_threshold",
                "context_drawdown_guard_min_entry_margin",
                "context_drawdown_guard_recover_after_pnl_recovery",
                "interaction_context_columns",
                "short_gap_threshold",
            ],
            dropna=False,
        )
        .agg(
            months=("month", "nunique"),
            trades=("trade_count", "sum"),
            total_adjusted_pnl=("total_adjusted_pnl", "sum"),
            worst_month_pnl=("total_adjusted_pnl", "min"),
            max_monthly_drawdown=("max_drawdown", "max"),
            forced_exits=("forced_exit_count", "sum"),
            short_adjusted_pnl=("short_adjusted_pnl", "sum"),
            long_adjusted_pnl=("long_adjusted_pnl", "sum"),
            active_signal_count=("active_signal_count", "sum"),
            active_trade_count=("active_trade_count", "sum"),
            active_trade_pnl=("active_trade_pnl", "sum"),
            inactive_trade_pnl=("inactive_trade_pnl", "sum"),
            guard_rule_count=("guard_rule_count", "sum"),
        )
        .reset_index()
        .sort_values(["total_adjusted_pnl", "worst_month_pnl"], ascending=[False, False])
    )


def apply_interaction_guard(
    *,
    run_paths: list[Path],
    data_path: Path,
    output_dir: Path,
    label: str,
    thresholds: list[float],
    min_entry_margins: list[float],
    recover_after_pnl_recovery_values: list[bool],
    context_columns: tuple[str, ...],
    match_modes: list[str],
    short_gap_thresholds: list[float],
    warmup_days: int,
    post_days: int,
) -> Path:
    root = make_run_dir(output_dir, label)
    ohlcv = read_ohlcv(data_path)
    rows: list[dict[str, Any]] = []

    for source_run in run_paths:
        config = load_run_config(source_run)
        backtest_config = restore_backtest_config(config["backtest_config"])
        base_policy_config = restore_model_policy_config(config["model_policy_config"])
        predictions = read_prediction_frame(base_policy_config.predictions, base_policy_config)
        df = slice_for_month(
            ohlcv,
            start=backtest_config.evaluation_start,
            end=backtest_config.evaluation_end,
            warmup_days=warmup_days,
            post_days=post_days,
            max_holding=backtest_config.max_holding,
        )
        month = backtest_config.evaluation_start.strftime("%Y-%m")
        signal = model_signal_from_predictions(df, predictions, base_policy_config)
        entry_margin = model_policy_entry_margin(df, predictions, base_policy_config)
        guard_rule_count = len(base_policy_config.side_ev_penalty_rules)

        for match_mode in match_modes:
            active_short_gap_thresholds = (
                short_gap_thresholds
                if match_mode == "signal_short_raw_gap"
                else [float("nan")]
            )
            for short_gap_threshold in active_short_gap_thresholds:
                entry_context, active_mask = interaction_entry_context(
                    df,
                    predictions,
                    base_policy_config,
                    signal,
                    context_columns=context_columns,
                    match_mode=match_mode,
                    short_gap_threshold=(
                        0.0 if pd.isna(short_gap_threshold) else short_gap_threshold
                    ),
                )
                active_signal_count = int((active_mask & signal.ne(0)).sum())
                for threshold in thresholds:
                    for min_entry_margin in min_entry_margins:
                        for recover_after_pnl_recovery in recover_after_pnl_recovery_values:
                            trades = trades_to_frame(
                                run_backtest(
                                    df,
                                    signal,
                                    backtest_config,
                                    entry_context=entry_context,
                                    entry_margin=entry_margin,
                                    context_drawdown_guard_loss_threshold=threshold,
                                    context_drawdown_guard_min_entry_margin=min_entry_margin,
                                    context_drawdown_guard_recover_after_pnl_recovery=(
                                        recover_after_pnl_recovery
                                    ),
                                    context_drawdown_guard_reset_monthly=True,
                                )
                            )
                            active_by_decision_timestamp = pd.Series(
                                active_mask.to_numpy(),
                                index=pd.to_datetime(df["timestamp"], utc=True),
                            )
                            if trades.empty:
                                active_trade_mask = pd.Series(False, index=trades.index)
                            else:
                                active_trade_mask = (
                                    pd.to_datetime(
                                        trades["entry_decision_timestamp"],
                                        utc=True,
                                    )
                                    .map(active_by_decision_timestamp)
                                    .fillna(False)
                                    .astype(bool)
                                )
                            metrics = summarize_trades(
                                trades,
                                backtest_config,
                                f"model_{base_policy_config.policy}",
                            )
                            metrics["prediction_rows"] = int(len(predictions))
                            metrics["signal_long_count"] = int((signal == 1).sum())
                            metrics["signal_short_count"] = int((signal == -1).sum())
                            metrics["signal_flat_count"] = int((signal == 0).sum())
                            curve = equity_curve(trades, backtest_config.evaluation_start)
                            gap_label = (
                                "na"
                                if pd.isna(short_gap_threshold)
                                else threshold_label(short_gap_threshold)
                            )
                            run_dir = (
                                root
                                / f"match_{match_mode}"
                                / f"short_gap_{gap_label}"
                                / f"threshold_{threshold_label(threshold)}"
                                / f"min_margin_{threshold_label(min_entry_margin)}"
                                / f"recover_{str(recover_after_pnl_recovery).lower()}"
                                / source_run.name
                            )
                            write_result(
                                run_dir,
                                metrics,
                                trades,
                                curve,
                                None,
                                backtest_config,
                                ModelPolicyConfig(
                                    **{
                                        **base_policy_config.__dict__,
                                        "context_drawdown_guard_loss_threshold": threshold,
                                        "context_drawdown_guard_min_entry_margin": (
                                            min_entry_margin
                                        ),
                                        "context_drawdown_guard_recover_after_pnl_recovery": (
                                            recover_after_pnl_recovery
                                        ),
                                        "context_drawdown_guard_context_columns": context_columns,
                                        "context_drawdown_guard_reset_monthly": True,
                                    }
                                ),
                            )
                            pd.DataFrame(
                                {
                                    "timestamp": df["timestamp"],
                                    "desired_position": signal,
                                    "side_rule_active": active_mask,
                                    "entry_context": entry_context,
                                    "entry_margin": entry_margin,
                                }
                            ).to_csv(
                                run_dir / "interaction_signal_context.csv",
                                index=False,
                            )
                            rows.append(
                                {
                                    "source_run": str(source_run),
                                    "month": month,
                                    "match_mode": match_mode,
                                    "short_gap_threshold": short_gap_threshold,
                                    "context_drawdown_guard_loss_threshold": threshold,
                                    "context_drawdown_guard_min_entry_margin": (
                                        min_entry_margin
                                    ),
                                    "context_drawdown_guard_recover_after_pnl_recovery": (
                                        recover_after_pnl_recovery
                                    ),
                                    "interaction_context_columns": ",".join(
                                        context_columns
                                    ),
                                    "active_signal_count": active_signal_count,
                                    "active_trade_count": int(active_trade_mask.sum()),
                                    "active_trade_pnl": float(
                                        trades.loc[
                                            active_trade_mask,
                                            "adjusted_pnl",
                                        ].sum()
                                    )
                                    if not trades.empty
                                    else 0.0,
                                    "inactive_trade_pnl": float(
                                        trades.loc[
                                            ~active_trade_mask,
                                            "adjusted_pnl",
                                        ].sum()
                                    )
                                    if not trades.empty
                                    else 0.0,
                                    "guard_rule_count": guard_rule_count,
                                    **metrics,
                                    "run_dir": str(run_dir),
                                }
                            )

    summary = pd.DataFrame(rows)
    summary.to_csv(root / "summary_by_run.csv", index=False)
    aggregate = aggregate_summary(summary)
    aggregate.to_csv(root / "summary_by_variant.csv", index=False)
    config = {
        "runs": [str(path) for path in run_paths],
        "data": data_path,
        "output_dir": output_dir,
        "label": label,
        "thresholds": thresholds,
        "min_entry_margins": min_entry_margins,
        "recover_after_pnl_recovery_values": recover_after_pnl_recovery_values,
        "context_columns": context_columns,
        "match_modes": match_modes,
        "short_gap_thresholds": short_gap_thresholds,
        "warmup_days": warmup_days,
        "post_days": post_days,
        "rows": int(len(summary)),
    }
    (root / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    print(aggregate.to_string(index=False))
    print(f"artifacts: {root}")
    return root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=parse_csv_paths, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="side_context_interaction_guard")
    parser.add_argument("--thresholds", type=parse_csv_floats, default=[20.0, 40.0, 60.0])
    parser.add_argument("--min-entry-margins", type=parse_csv_floats, default=[20.0])
    parser.add_argument(
        "--recover-after-pnl-recovery-values",
        type=parse_csv_bools,
        default=[False],
    )
    parser.add_argument(
        "--context-columns",
        type=parse_csv_string_tuple,
        default=("dataset_month",),
    )
    parser.add_argument(
        "--match-modes",
        type=parse_csv_strings,
        default=["any_rule", "selected_side_rule"],
    )
    parser.add_argument("--short-gap-thresholds", type=parse_csv_floats, default=[0.0])
    parser.add_argument("--warmup-days", type=int, default=7)
    parser.add_argument("--post-days", type=int, default=4)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    apply_interaction_guard(
        run_paths=expand_run_paths(args.runs),
        data_path=args.data,
        output_dir=args.output_dir,
        label=args.label,
        thresholds=args.thresholds,
        min_entry_margins=args.min_entry_margins,
        recover_after_pnl_recovery_values=args.recover_after_pnl_recovery_values,
        context_columns=args.context_columns,
        match_modes=args.match_modes,
        short_gap_thresholds=args.short_gap_thresholds,
        warmup_days=args.warmup_days,
        post_days=args.post_days,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
