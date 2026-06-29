#!/usr/bin/env python3
"""Apply online context drawdown guard thresholds to existing model-policy runs."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

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
    parse_csv_floats,
    parse_csv_paths,
    parse_csv_string_tuple,
    read_ohlcv,
    run_model_policy,
    slice_for_month,
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


def local_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return json_default(value)


def expand_run_paths(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if (path / "config.json").exists():
            expanded.append(path)
            continue
        if not path.is_dir():
            raise FileNotFoundError(f"run path not found: {path}")
        children = sorted(child for child in path.iterdir() if (child / "config.json").exists())
        if not children:
            raise FileNotFoundError(f"no model-policy run dirs under: {path}")
        expanded.extend(children)
    return expanded


def load_run_config(path: Path) -> dict[str, Any]:
    with (path / "config.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
    return str(value).replace("-", "m").replace(".", "p")


def apply_thresholds(
    *,
    run_paths: list[Path],
    data_path: Path,
    output_dir: Path,
    label: str,
    thresholds: list[float],
    context_columns: tuple[str, ...],
    reset_monthly: bool,
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
        df = slice_for_month(
            ohlcv,
            start=backtest_config.evaluation_start,
            end=backtest_config.evaluation_end,
            warmup_days=warmup_days,
            post_days=post_days,
            max_holding=backtest_config.max_holding,
        )
        month = backtest_config.evaluation_start.strftime("%Y-%m")
        for threshold in thresholds:
            policy_config = restore_model_policy_config(config["model_policy_config"])
            policy_config = ModelPolicyConfig(
                **{
                    **base_policy_config.__dict__,
                    "context_drawdown_guard_loss_threshold": threshold,
                    "context_drawdown_guard_context_columns": context_columns,
                    "context_drawdown_guard_reset_monthly": reset_monthly,
                }
            )
            metrics, trades, _, signal = run_model_policy(
                df,
                backtest_config,
                policy_config,
            )
            curve = equity_curve(trades, backtest_config.evaluation_start)
            run_dir = root / f"threshold_{threshold_label(threshold)}" / source_run.name
            write_result(run_dir, metrics, trades, curve, None, backtest_config, policy_config)
            pd.DataFrame({"timestamp": df["timestamp"], "desired_position": signal}).to_csv(
                run_dir / "desired_position.csv",
                index=False,
            )
            rows.append(
                {
                    "source_run": str(source_run),
                    "month": month,
                    "context_drawdown_guard_loss_threshold": threshold,
                    "context_drawdown_guard_context_columns": ",".join(context_columns),
                    "context_drawdown_guard_reset_monthly": reset_monthly,
                    **metrics,
                    "run_dir": str(run_dir),
                }
            )

    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary.to_csv(root / "summary_by_run.csv", index=False)
        aggregate = (
            summary.groupby(
                [
                    "context_drawdown_guard_loss_threshold",
                    "context_drawdown_guard_context_columns",
                    "context_drawdown_guard_reset_monthly",
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
            )
            .reset_index()
            .sort_values("total_adjusted_pnl", ascending=False)
        )
        aggregate.to_csv(root / "summary_by_threshold.csv", index=False)
        print(aggregate.to_string(index=False))

    metadata = {
        "runs": [str(path) for path in run_paths],
        "data": data_path,
        "thresholds": thresholds,
        "context_columns": context_columns,
        "reset_monthly": reset_monthly,
        "warmup_days": warmup_days,
        "post_days": post_days,
    }
    (root / "config.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    print(f"artifacts: {root}")
    return root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply online context drawdown guard thresholds to existing runs.",
    )
    parser.add_argument("--runs", type=parse_csv_paths, required=True)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/processed/histdata/xauusd/xauusd_m1.parquet"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="context_drawdown_guard_apply")
    parser.add_argument("--thresholds", default="inf,20,40,60,80")
    parser.add_argument(
        "--context-columns",
        default="combined_regime,session_regime",
        help="comma-separated prediction columns used with direction as context",
    )
    parser.add_argument(
        "--reset-monthly",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--warmup-days", type=int, default=7)
    parser.add_argument("--post-days", type=int, default=4)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_paths = expand_run_paths(args.runs)
    apply_thresholds(
        run_paths=run_paths,
        data_path=args.data,
        output_dir=args.output_dir,
        label=args.label,
        thresholds=parse_csv_floats(args.thresholds),
        context_columns=parse_csv_string_tuple(args.context_columns),
        reset_monthly=args.reset_monthly,
        warmup_days=args.warmup_days,
        post_days=args.post_days,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
