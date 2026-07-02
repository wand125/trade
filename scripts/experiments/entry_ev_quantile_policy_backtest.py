#!/usr/bin/env python3
"""Backtest entry-EV quantile admission policies across chronological families."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
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
    json_default,
    make_run_dir,
    month_bounds,
    read_ohlcv,
    run_model_policy,
    slice_for_month,
)


DEFAULT_POLICY_CANDIDATES = (
    "abs_entry10_short9_side5_rank0",
    "q99_sg95_rank90_side_regime_session_month",
    "q95_sg95_rank90_side_regime_session_month",
    "q99_sg90_rank90_side_regime_session_month",
    "q99_sg95_rank0_side_regime_session_month",
    "q99_sg95_rank90_side_month",
    "q99_sg95_rank90_month",
)


@dataclass(frozen=True)
class PolicyCandidate:
    name: str
    scope: str = ""
    score_quantile: float = 0.0
    side_gap_quantile: float = 0.0
    rank_quantile: float = 0.0
    entry_threshold: float = 0.0
    short_entry_threshold_offset: float = 0.0
    side_margin: float = 0.0
    min_entry_rank: float = 0.0


def local_json_default(value: Any) -> Any:
    try:
        return json_default(value)
    except TypeError:
        pass
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timedelta):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


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


def parse_optional_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_policy_candidates(value: str) -> list[str]:
    names = parse_optional_csv(value)
    invalid: list[str] = []
    for name in names:
        try:
            policy_candidate_from_name(name)
        except ValueError:
            invalid.append(name)
    if invalid:
        raise argparse.ArgumentTypeError(
            f"unknown policy candidates: {','.join(sorted(invalid))}"
        )
    return names


def parse_role_months(values: list[str]) -> dict[tuple[str, str], str]:
    role_lookup: dict[tuple[str, str], str] = {}
    for value in values:
        if "=" not in value or ":" not in value:
            raise argparse.ArgumentTypeError(
                "role months must use role=family:YYYY-MM,YYYY-MM"
            )
        role, family_months = value.split("=", 1)
        family, months_value = family_months.split(":", 1)
        role = role.strip()
        family = family.strip()
        months = parse_optional_csv(months_value)
        if not role or not family or not months:
            raise argparse.ArgumentTypeError(
                "role, family, and at least one month are required"
            )
        for month in months:
            role_lookup[(family, month)] = role
    return role_lookup


def quantile_column(score_kind: str, metric: str, scope: str) -> str:
    return f"pred_{score_kind}_{metric}_pct_{scope}"


def parse_candidate_number(value: str) -> float:
    return float(value.replace("p", "."))


def policy_candidate_from_name(name: str) -> PolicyCandidate:
    if name == "abs_entry10_short9_side5_rank0":
        return PolicyCandidate(
            name=name,
            entry_threshold=10.0,
            short_entry_threshold_offset=9.0,
            side_margin=5.0,
            min_entry_rank=0.0,
        )

    parts = name.split("_")
    if len(parts) < 4 or not parts[0].startswith("q") or not parts[1].startswith("sg"):
        raise ValueError(f"unknown policy candidate: {name}")
    rank_part = parts[2]
    if not rank_part.startswith("rank"):
        raise ValueError(f"unknown policy candidate: {name}")
    rank_quantile = parse_candidate_number(rank_part[4:]) / 100.0
    entry_threshold = 0.0
    scope_parts = parts[3:]
    if scope_parts and scope_parts[0].startswith("floor"):
        entry_threshold = parse_candidate_number(scope_parts[0][5:])
        scope_parts = scope_parts[1:]
    if not scope_parts:
        raise ValueError(f"unknown policy candidate: {name}")
    score_quantile = parse_candidate_number(parts[0][1:]) / 100.0
    side_gap_quantile = parse_candidate_number(parts[1][2:]) / 100.0
    if (
        not 0 <= score_quantile <= 1
        or not 0 <= side_gap_quantile <= 1
        or not 0 <= rank_quantile <= 1
    ):
        raise ValueError(f"unknown policy candidate: {name}")
    if entry_threshold < 0:
        raise ValueError(f"unknown policy candidate: {name}")
    scope = "_".join(scope_parts)
    return PolicyCandidate(
        name=name,
        scope=scope,
        score_quantile=score_quantile,
        side_gap_quantile=side_gap_quantile,
        rank_quantile=rank_quantile,
        entry_threshold=entry_threshold,
    )


def prediction_months(predictions: pd.DataFrame) -> list[str]:
    if "dataset_month" in predictions.columns:
        months = predictions["dataset_month"].astype(str).str.slice(0, 7)
    else:
        months = pd.to_datetime(
            predictions["decision_timestamp"],
            utc=True,
        ).dt.strftime("%Y-%m")
    return sorted(month for month in months.dropna().unique().tolist() if month)


def build_model_policy_config(
    *,
    prediction_path: Path,
    candidate: PolicyCandidate,
    score_kind: str,
    long_column: str,
    short_column: str,
    long_holding_column: str,
    short_holding_column: str,
    min_valid_predicted_hold_minutes: float,
    max_predicted_hold_minutes: float,
    long_loss_first_column: str = "pred_long_exit_event_prob_2",
    short_loss_first_column: str = "pred_short_exit_event_prob_2",
    side_block_rules: tuple[str, ...] = (),
) -> ModelPolicyConfig:
    return ModelPolicyConfig(
        predictions=prediction_path,
        policy="timed_ev",
        entry_threshold=candidate.entry_threshold,
        short_entry_threshold_offset=candidate.short_entry_threshold_offset,
        side_margin=candidate.side_margin,
        long_column=long_column,
        short_column=short_column,
        long_holding_column=long_holding_column,
        short_holding_column=short_holding_column,
        long_loss_first_column=long_loss_first_column,
        short_loss_first_column=short_loss_first_column,
        min_valid_predicted_hold_minutes=min_valid_predicted_hold_minutes,
        max_predicted_hold_minutes=max_predicted_hold_minutes,
        min_entry_rank=candidate.min_entry_rank,
        min_entry_score_quantile=candidate.score_quantile,
        min_side_gap_quantile=candidate.side_gap_quantile,
        min_entry_rank_quantile=candidate.rank_quantile,
        side_block_rules=side_block_rules,
        entry_score_quantile_column=(
            quantile_column(score_kind, "selected_score", candidate.scope)
            if candidate.score_quantile > 0
            else ""
        ),
        side_gap_quantile_column=(
            quantile_column(score_kind, "side_gap", candidate.scope)
            if candidate.side_gap_quantile > 0
            else ""
        ),
        entry_rank_quantile_column=(
            quantile_column(score_kind, "selected_entry_rank", candidate.scope)
            if candidate.rank_quantile > 0
            else ""
        ),
    )


def build_backtest_config(
    *,
    month: str,
    max_hold_hours: float,
    profit_multiplier: float,
    loss_multiplier: float,
    spread_points: float,
    slippage_points: float,
    execution_delay_bars: int,
) -> BacktestConfig:
    start, end = month_bounds(month)
    return BacktestConfig(
        evaluation_start=start,
        evaluation_end=end,
        max_holding=pd.Timedelta(hours=max_hold_hours),
        profit_multiplier=profit_multiplier,
        loss_multiplier=loss_multiplier,
        spread_points=spread_points,
        slippage_points=slippage_points,
        execution_delay_bars=execution_delay_bars,
    )


def summarize_by_group(monthly: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if monthly.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for key, group in monthly.groupby(group_columns, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_columns, key))
        adjusted = group["total_adjusted_pnl"].astype(float)
        trade_count = group["trade_count"].astype(float)
        row.update(
            {
                "month_count": int(group["month"].nunique()),
                "active_months": int((trade_count > 0).sum()),
                "total_adjusted_pnl_sum": float(adjusted.sum()),
                "total_adjusted_pnl_min": float(adjusted.min()),
                "total_adjusted_pnl_mean": float(adjusted.mean()),
                "trade_count_sum": int(trade_count.sum()),
                "trade_count_min": int(trade_count.min()),
                "max_drawdown_max": float(group["max_drawdown"].astype(float).max()),
                "long_trade_count_sum": int(group["long_trade_count"].astype(float).sum()),
                "short_trade_count_sum": int(group["short_trade_count"].astype(float).sum()),
                "signal_long_count_sum": int(group["signal_long_count"].astype(float).sum()),
                "signal_short_count_sum": int(group["signal_short_count"].astype(float).sum()),
            }
        )
        total_trades = row["trade_count_sum"]
        row["long_trade_share"] = (
            float(row["long_trade_count_sum"] / total_trades) if total_trades else 0.0
        )
        row["short_trade_share"] = (
            float(row["short_trade_count_sum"] / total_trades) if total_trades else 0.0
        )
        row["max_side_trade_share"] = max(
            row["long_trade_share"],
            row["short_trade_share"],
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["total_adjusted_pnl_min", "total_adjusted_pnl_sum", "trade_count_sum"],
        ascending=[False, False, False],
    )


def run_quantile_policy_backtests(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    candidate_names = parse_policy_candidates(args.policy_candidates)
    role_lookup = parse_role_months(args.role_months)
    candidates = [policy_candidate_from_name(name) for name in candidate_names]
    requested_months = set(parse_optional_csv(args.months))
    run_dir = make_run_dir(args.output_dir, args.label)
    price_data = read_ohlcv(args.data)

    monthly_rows: list[dict[str, Any]] = []
    config_rows = [asdict(candidate) for candidate in candidates]

    for family, prediction_path in family_predictions.items():
        predictions = pd.read_parquet(prediction_path)
        months = prediction_months(predictions)
        if requested_months:
            months = [month for month in months if month in requested_months]
        if not months:
            raise ValueError(f"no evaluation months for family: {family}")

        for candidate in candidates:
            model_config = build_model_policy_config(
                prediction_path=prediction_path,
                candidate=candidate,
                score_kind=args.score_kind,
                long_column=args.long_column,
                short_column=args.short_column,
                long_holding_column=args.long_holding_column,
                short_holding_column=args.short_holding_column,
                min_valid_predicted_hold_minutes=args.min_valid_predicted_hold_minutes,
                max_predicted_hold_minutes=args.max_predicted_hold_minutes,
                side_block_rules=tuple(parse_optional_csv(args.side_block_rules)),
            )
            for month in months:
                backtest_config = build_backtest_config(
                    month=month,
                    max_hold_hours=args.max_hold_hours,
                    profit_multiplier=args.profit_multiplier,
                    loss_multiplier=args.loss_multiplier,
                    spread_points=args.spread_points,
                    slippage_points=args.slippage_points,
                    execution_delay_bars=args.execution_delay_bars,
                )
                df = slice_for_month(
                    price_data,
                    start=backtest_config.evaluation_start,
                    end=backtest_config.evaluation_end,
                    warmup_days=args.warmup_days,
                    post_days=args.post_days,
                    max_holding=backtest_config.max_holding,
                )
                metrics, trades, _curve, signal = run_model_policy(
                    df,
                    backtest_config,
                    model_config,
                    predictions=predictions,
                )
                row: dict[str, Any] = {
                    "family": family,
                    "role": role_lookup.get((family, month), family),
                    "month": month,
                    "candidate": candidate.name,
                    **asdict(candidate),
                    **metrics,
                }
                monthly_rows.append(row)
                if args.write_trades:
                    trade_path = run_dir / "trades" / family / candidate.name
                    trade_path.mkdir(parents=True, exist_ok=True)
                    trades.to_csv(trade_path / f"{month}.csv", index=False)
                    pd.DataFrame(
                        {
                            "timestamp": df["timestamp"],
                            "desired_position": signal,
                        }
                    ).to_csv(trade_path / f"{month}_desired_position.csv", index=False)

    monthly = pd.DataFrame(monthly_rows)
    monthly.to_csv(run_dir / "monthly_policy_metrics.csv", index=False)
    pd.DataFrame(config_rows).to_csv(run_dir / "policy_candidates.csv", index=False)
    family_summary = summarize_by_group(monthly, ["family", "candidate"])
    family_summary.to_csv(run_dir / "family_policy_summary.csv", index=False)
    role_summary = summarize_by_group(monthly, ["role", "candidate"])
    role_summary.to_csv(run_dir / "role_policy_summary.csv", index=False)
    overall_summary = summarize_by_group(monthly, ["candidate"])
    overall_summary.to_csv(run_dir / "overall_policy_summary.csv", index=False)

    config = {
        "family_predictions": family_predictions,
        "policy_candidates": candidate_names,
        "role_months": args.role_months,
        "data": args.data,
        "score_kind": args.score_kind,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_holding_column": args.long_holding_column,
        "short_holding_column": args.short_holding_column,
        "min_valid_predicted_hold_minutes": args.min_valid_predicted_hold_minutes,
        "max_predicted_hold_minutes": args.max_predicted_hold_minutes,
        "max_hold_hours": args.max_hold_hours,
        "profit_multiplier": args.profit_multiplier,
        "loss_multiplier": args.loss_multiplier,
        "spread_points": args.spread_points,
        "slippage_points": args.slippage_points,
        "execution_delay_bars": args.execution_delay_bars,
        "warmup_days": args.warmup_days,
        "post_days": args.post_days,
        "months": sorted(requested_months),
        "write_trades": args.write_trades,
        "side_block_rules": parse_optional_csv(args.side_block_rules),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Family summary:")
    print(
        family_summary[
            [
                "family",
                "candidate",
                "total_adjusted_pnl_sum",
                "total_adjusted_pnl_min",
                "trade_count_sum",
                "max_drawdown_max",
                "max_side_trade_share",
            ]
        ].to_string(index=False)
    )
    print("\nRole summary:")
    print(
        role_summary[
            [
                "role",
                "candidate",
                "total_adjusted_pnl_sum",
                "total_adjusted_pnl_min",
                "trade_count_sum",
                "max_drawdown_max",
                "max_side_trade_share",
            ]
        ].to_string(index=False)
    )
    print("\nOverall summary:")
    print(
        overall_summary[
            [
                "candidate",
                "total_adjusted_pnl_sum",
                "total_adjusted_pnl_min",
                "trade_count_sum",
                "max_drawdown_max",
                "max_side_trade_share",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--family-predictions",
        action="append",
        required=True,
        help="family=prediction parquet; can be repeated",
    )
    parser.add_argument(
        "--policy-candidates",
        default=",".join(DEFAULT_POLICY_CANDIDATES),
        help="comma-separated built-in policy candidates",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/processed/histdata/xauusd/xauusd_m1.parquet"),
    )
    parser.add_argument("--months", default="", help="optional comma-separated months")
    parser.add_argument(
        "--role-months",
        action="append",
        default=[],
        help="role=family:YYYY-MM,YYYY-MM mapping for role_policy_summary.csv",
    )
    parser.add_argument("--score-kind", default="calibrated")
    parser.add_argument("--long-column", default="pred_calibrated_long_best_adjusted_pnl")
    parser.add_argument("--short-column", default="pred_calibrated_short_best_adjusted_pnl")
    parser.add_argument("--long-holding-column", default="pred_mlp_long_exit_event_minutes")
    parser.add_argument("--short-holding-column", default="pred_mlp_short_exit_event_minutes")
    parser.add_argument("--min-valid-predicted-hold-minutes", type=float, default=30.0)
    parser.add_argument("--max-predicted-hold-minutes", type=float, default=260.0)
    parser.add_argument("--max-hold-hours", type=float, default=24.0)
    parser.add_argument("--profit-multiplier", type=float, default=1.0)
    parser.add_argument("--loss-multiplier", type=float, default=1.2)
    parser.add_argument("--spread-points", type=float, default=0.0)
    parser.add_argument("--slippage-points", type=float, default=0.0)
    parser.add_argument("--execution-delay-bars", type=int, default=0)
    parser.add_argument("--warmup-days", type=int, default=7)
    parser.add_argument("--post-days", type=int, default=4)
    parser.add_argument("--write-trades", action="store_true")
    parser.add_argument(
        "--side-block-rules",
        default="",
        help="comma-separated side block rules, e.g. short:column=value",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    parser.add_argument("--label", default="entry_ev_quantile_policy_backtest")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_quantile_policy_backtests(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
