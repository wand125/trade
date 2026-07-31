#!/usr/bin/env python3
"""Evaluate exit-holding caps driven by pred-hit/q75 overestimate interaction."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

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
    write_result,
)


STATEFUL_PREFIX = "pred_stateful_risk_wf_exp_session_mm_walkforward_floor_lowered"
PREDHIT_PREFIX = "pred_trade_failure_pred_hit_actual_miss"
Q75_PREFIX = "pred_trade_overestimate_high_q75"


def parse_csv_floats(value: str) -> list[float]:
    values = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one float is required")
    return values


def parse_csv_paths(value: str) -> list[Path]:
    values = [Path(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one path is required")
    return values


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one string is required")
    return values


def parse_optional_csv_strings(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_side_modes(value: str) -> list[str]:
    values = parse_csv_strings(value)
    allowed = {"both", "long_only", "short_only"}
    invalid = sorted(set(values) - allowed)
    if invalid:
        raise argparse.ArgumentTypeError(f"invalid side modes: {', '.join(invalid)}")
    return values


def parse_combined_session_pairs(value: str) -> list[tuple[str, str]]:
    if not value:
        return []
    pairs: list[tuple[str, str]] = []
    for part in value.split(","):
        raw = part.strip()
        if not raw:
            continue
        if ":" not in raw:
            raise argparse.ArgumentTypeError(
                f"combined/session pair must use combined_regime:session_regime: {raw}"
            )
        combined, session = [piece.strip() for piece in raw.split(":", 1)]
        if not combined or not session:
            raise argparse.ArgumentTypeError(
                f"combined/session pair must use combined_regime:session_regime: {raw}"
            )
        pairs.append((combined, session))
    return pairs


def read_month_context_pairs(
    path: Path | None,
    *,
    selection_scope: str,
    scope: str,
) -> list[tuple[str, str, str]]:
    if path is None:
        return []
    frame = pd.read_csv(path)
    required = {"target_month", "combined_regime", "session_regime"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
    if "selection_scope" in frame.columns:
        frame = frame[frame["selection_scope"].astype(str).eq(selection_scope)].copy()
    if "scope" in frame.columns:
        frame = frame[frame["scope"].astype(str).eq(scope)].copy()
    rows = frame[["target_month", "combined_regime", "session_regime"]].drop_duplicates()
    return [
        (str(row.target_month), str(row.combined_regime), str(row.session_regime))
        for row in rows.itertuples(index=False)
    ]


def value_label(value: float) -> str:
    return f"{value:g}".replace(".", "p").replace("-", "m")


def require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"predictions are missing columns: {', '.join(missing)}")


def read_filtered_predictions(paths: list[Path], months: list[str]) -> pd.DataFrame:
    frames = []
    for path in paths:
        frame = pd.read_parquet(path)
        if "dataset_month" not in frame.columns:
            raise ValueError(f"{path} is missing dataset_month")
        frame = frame[frame["dataset_month"].astype(str).isin(months)].copy()
        if not frame.empty:
            frame["source_path"] = str(path)
            frames.append(frame)
    if not frames:
        raise ValueError("no prediction rows matched requested months")
    combined = pd.concat(frames, ignore_index=True)
    combined["decision_timestamp"] = pd.to_datetime(combined["decision_timestamp"], utc=True)
    duplicated = combined["decision_timestamp"].duplicated()
    if duplicated.any():
        duplicate_months = combined.loc[duplicated, "dataset_month"].astype(str).value_counts().to_dict()
        raise ValueError(f"combined predictions contain duplicate decision timestamps: {duplicate_months}")
    missing_months = sorted(set(months) - set(combined["dataset_month"].astype(str).unique()))
    if missing_months:
        raise ValueError(f"combined predictions missing months: {', '.join(missing_months)}")
    return combined.sort_values("decision_timestamp").reset_index(drop=True)


def positive_interaction_risk(frame: pd.DataFrame, side: str) -> pd.Series:
    predhit = pd.to_numeric(frame[f"{PREDHIT_PREFIX}_{side}_prob"], errors="raise").clip(0.0, 1.0)
    q75 = pd.to_numeric(frame[f"{Q75_PREFIX}_{side}_prob"], errors="raise").clip(0.0, 1.0)
    return predhit * q75


def add_holding_cap_columns(
    frame: pd.DataFrame,
    *,
    threshold_frame: pd.DataFrame,
    threshold_quantiles: list[float],
    caps: list[float],
    side_modes: list[str],
    include_combined_regimes: list[str],
    exclude_combined_regimes: list[str],
    include_combined_session_pairs: list[tuple[str, str]],
    exclude_combined_session_pairs: list[tuple[str, str]],
    exclude_combined_session_pairs_by_month: list[tuple[str, str, str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = frame.copy()
    required = [
        "pred_mlp_long_exit_event_minutes",
        "pred_mlp_short_exit_event_minutes",
    ] + [
        f"{prefix}_{side}_prob"
        for prefix in (PREDHIT_PREFIX, Q75_PREFIX)
        for side in ("long", "short")
    ]
    require_columns(output, required)
    require_columns(threshold_frame, required[2:])
    if include_combined_regimes or exclude_combined_regimes:
        require_columns(output, ["combined_regime"])
    if include_combined_session_pairs or exclude_combined_session_pairs:
        require_columns(output, ["combined_regime", "session_regime"])
    if exclude_combined_session_pairs_by_month:
        require_columns(output, ["dataset_month", "combined_regime", "session_regime"])
    context_mask = pd.Series(True, index=output.index)
    if include_combined_regimes:
        context_mask &= output["combined_regime"].astype(str).isin(include_combined_regimes)
    if exclude_combined_regimes:
        context_mask &= ~output["combined_regime"].astype(str).isin(exclude_combined_regimes)
    combined_values = output.get("combined_regime", pd.Series("", index=output.index)).astype(str)
    session_values = output.get("session_regime", pd.Series("", index=output.index)).astype(str)
    if include_combined_session_pairs:
        pair_mask = pd.Series(False, index=output.index)
        for combined, session in include_combined_session_pairs:
            pair_mask |= combined_values.eq(combined) & session_values.eq(session)
        context_mask &= pair_mask
    if exclude_combined_session_pairs:
        pair_mask = pd.Series(False, index=output.index)
        for combined, session in exclude_combined_session_pairs:
            pair_mask |= combined_values.eq(combined) & session_values.eq(session)
        context_mask &= ~pair_mask
    if exclude_combined_session_pairs_by_month:
        month_values = output["dataset_month"].astype(str)
        pair_mask = pd.Series(False, index=output.index)
        for month, combined, session in exclude_combined_session_pairs_by_month:
            pair_mask |= month_values.eq(month) & combined_values.eq(combined) & session_values.eq(session)
        context_mask &= ~pair_mask

    threshold_rows: list[dict[str, object]] = []
    for side in ("long", "short"):
        live_risk = positive_interaction_risk(output, side)
        threshold_risk = positive_interaction_risk(threshold_frame, side)
        holding = pd.to_numeric(output[f"pred_mlp_{side}_exit_event_minutes"], errors="raise")
        for quantile in threshold_quantiles:
            threshold = float(threshold_risk.quantile(quantile))
            high_risk = (live_risk >= threshold) & context_mask
            threshold_rows.append(
                {
                    "side": side,
                    "threshold_quantile": quantile,
                    "threshold": threshold,
                    "threshold_source_rows": int(len(threshold_risk)),
                    "include_combined_regimes": ",".join(include_combined_regimes),
                    "exclude_combined_regimes": ",".join(exclude_combined_regimes),
                    "include_combined_session_pairs": ",".join(
                        f"{combined}:{session}" for combined, session in include_combined_session_pairs
                    ),
                    "exclude_combined_session_pairs": ",".join(
                        f"{combined}:{session}" for combined, session in exclude_combined_session_pairs
                    ),
                    "exclude_combined_session_pairs_by_month": ",".join(
                        f"{month}:{combined}:{session}"
                        for month, combined, session in exclude_combined_session_pairs_by_month
                    ),
                    "active_rows": int(high_risk.sum()),
                    "active_rate": float(high_risk.mean()),
                    "active_mean_risk": float(live_risk[high_risk].mean()) if high_risk.any() else 0.0,
                    "all_mean_risk": float(live_risk.mean()),
                }
            )
            q_label = value_label(quantile)
            for cap in caps:
                cap_label = value_label(cap)
                for mode in side_modes:
                    if mode == "both":
                        column = f"pred_mlp_{side}_exit_event_minutes_predhit_q75_q{q_label}_cap{cap_label}"
                        should_cap_side = True
                    else:
                        column = (
                            f"pred_mlp_{side}_exit_event_minutes_predhit_q75_"
                            f"{mode}_q{q_label}_cap{cap_label}"
                        )
                        should_cap_side = (mode == "long_only" and side == "long") or (
                            mode == "short_only" and side == "short"
                        )
                    if should_cap_side:
                        capped = np.minimum(holding, cap)
                        output[column] = np.where(high_risk, capped, holding)
                    else:
                        output[column] = holding
    return output, pd.DataFrame(threshold_rows)


def base_policy_config(
    predictions_path: Path,
    *,
    risk_penalty: float,
    long_holding_column: str,
    short_holding_column: str,
) -> ModelPolicyConfig:
    return ModelPolicyConfig(
        predictions=predictions_path,
        policy="timed_ev",
        entry_threshold=12.0,
        short_entry_threshold_offset=6.0,
        side_margin=5.0,
        long_column="pred_long_best_adjusted_pnl",
        short_column="pred_short_best_adjusted_pnl",
        long_risk_column=f"{STATEFUL_PREFIX}_long_risk",
        short_risk_column=f"{STATEFUL_PREFIX}_short_risk",
        risk_penalty=risk_penalty,
        long_holding_column=long_holding_column,
        short_holding_column=short_holding_column,
        min_predicted_hold_minutes=1.0,
        max_predicted_hold_minutes=480.0,
        min_valid_predicted_hold_minutes=30.0,
        fixed_horizon_minutes=(60.0, 240.0, 720.0),
        long_fixed_horizon_columns=(
            "pred_long_fixed_60m_adjusted_pnl",
            "pred_long_fixed_240m_adjusted_pnl",
            "pred_long_fixed_720m_adjusted_pnl",
        ),
        short_fixed_horizon_columns=(
            "pred_short_fixed_60m_adjusted_pnl",
            "pred_short_fixed_240m_adjusted_pnl",
            "pred_short_fixed_720m_adjusted_pnl",
        ),
        fixed_horizon_score_mode="max",
        long_wait_regret_column="pred_long_wait_regret",
        short_wait_regret_column="pred_short_wait_regret",
        long_entry_rank_column="pred_long_entry_local_rank",
        short_entry_rank_column="pred_short_entry_local_rank",
        long_profit_barrier_column="pred_long_profit_barrier_hit",
        short_profit_barrier_column="pred_short_profit_barrier_hit",
        long_time_exit_column="pred_long_exit_event_prob_0",
        short_time_exit_column="pred_short_exit_event_prob_0",
        long_loss_first_column="pred_long_exit_event_prob_2",
        short_loss_first_column="pred_short_exit_event_prob_2",
        long_side_confidence_column="pred_best_side_prob_1",
        short_side_confidence_column="pred_best_side_prob_-1",
        long_trade_quality_column="pred_trade_quality_long_adjusted_pnl",
        short_trade_quality_column="pred_trade_quality_short_adjusted_pnl",
        min_entry_rank=0.5,
        side_ev_penalty_rules=(
            "short:combined_regime=down_low_vol:5",
            "short:combined_regime=up_low_vol:10",
        ),
    )


def policy_configs(
    predictions_path: Path,
    *,
    threshold_quantiles: list[float],
    caps: list[float],
    side_modes: list[str],
) -> list[tuple[str, ModelPolicyConfig]]:
    configs: list[tuple[str, ModelPolicyConfig]] = []
    base_long = "pred_mlp_long_exit_event_minutes"
    base_short = "pred_mlp_short_exit_event_minutes"
    configs.append(
        (
            "risk0",
            base_policy_config(
                predictions_path,
                risk_penalty=0.0,
                long_holding_column=base_long,
                short_holding_column=base_short,
            ),
        )
    )
    configs.append(
        (
            "baseline_risk5",
            base_policy_config(
                predictions_path,
                risk_penalty=5.0,
                long_holding_column=base_long,
                short_holding_column=base_short,
            ),
        )
    )
    for quantile in threshold_quantiles:
        q_label = value_label(quantile)
        for cap in caps:
            cap_label = value_label(cap)
            for mode in side_modes:
                if mode == "both":
                    long_column = f"pred_mlp_long_exit_event_minutes_predhit_q75_q{q_label}_cap{cap_label}"
                    short_column = f"pred_mlp_short_exit_event_minutes_predhit_q75_q{q_label}_cap{cap_label}"
                    label_prefix = f"holdcap_q{q_label}_cap{cap_label}"
                else:
                    long_column = (
                        f"pred_mlp_long_exit_event_minutes_predhit_q75_{mode}_q{q_label}_cap{cap_label}"
                    )
                    short_column = (
                        f"pred_mlp_short_exit_event_minutes_predhit_q75_{mode}_q{q_label}_cap{cap_label}"
                    )
                    label_prefix = f"holdcap_{mode}_q{q_label}_cap{cap_label}"
                for risk_label, risk_penalty in (("risk0", 0.0), ("risk5", 5.0)):
                    label = f"{label_prefix}_{risk_label}"
                    configs.append(
                        (
                            label,
                            base_policy_config(
                                predictions_path,
                                risk_penalty=risk_penalty,
                                long_holding_column=long_column,
                                short_holding_column=short_column,
                            ),
                        )
                    )
    return configs


def aggregate_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for label, group in metrics.groupby("label", sort=False):
        rows.append(
            {
                "label": label,
                "total_adjusted_pnl": float(group["total_adjusted_pnl"].sum()),
                "min_month_adjusted_pnl": float(group["total_adjusted_pnl"].min()),
                "max_monthly_drawdown": float(group["max_drawdown"].max()),
                "trade_count": int(group["trade_count"].sum()),
                "forced_exit_count": int(group["forced_exit_count"].sum()),
                "mean_win_rate": float(group["win_rate"].mean()),
                "months": ",".join(group["month"].astype(str)),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["total_adjusted_pnl", "min_month_adjusted_pnl"],
        ascending=[False, False],
    )


def serializable_policy_config(config: ModelPolicyConfig) -> dict[str, object]:
    data = asdict(config)
    data["predictions"] = str(config.predictions)
    return data


def run_policy_grid(
    *,
    predictions_path: Path,
    predictions: pd.DataFrame,
    months: list[str],
    data_path: Path,
    backtest_dir: Path,
    threshold_quantiles: list[float],
    caps: list[float],
    side_modes: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_data = read_ohlcv(data_path)
    metrics_rows: list[dict[str, object]] = []
    for label, config in policy_configs(
        predictions_path,
        threshold_quantiles=threshold_quantiles,
        caps=caps,
        side_modes=side_modes,
    ):
        for month in months:
            start, end = month_bounds(month)
            max_holding = pd.Timedelta(hours=24)
            data = slice_for_month(
                all_data,
                start=start,
                end=end,
                warmup_days=7,
                post_days=4,
                max_holding=max_holding,
            )
            backtest_config = BacktestConfig(
                evaluation_start=start,
                evaluation_end=end,
                max_holding=max_holding,
                profit_multiplier=1.0,
                loss_multiplier=1.2,
                spread_points=0.2,
                slippage_points=0.1,
                execution_delay_bars=1,
            )
            month_predictions = predictions[predictions["dataset_month"].astype(str).eq(month)].copy()
            metrics, trades, curve, signal = run_model_policy(
                data,
                backtest_config,
                config,
                predictions=month_predictions,
            )
            run_dir = make_run_dir(backtest_dir, f"{label}_{month}")
            write_result(
                run_dir,
                metrics,
                trades,
                curve,
                strategy_config=None,
                backtest_config=backtest_config,
                model_policy_config=config,
            )
            pd.DataFrame({"timestamp": data["timestamp"], "desired_position": signal}).to_csv(
                run_dir / "desired_position.csv",
                index=False,
            )
            metrics_rows.append(
                {
                    "label": label,
                    "month": month,
                    "run_dir": str(run_dir),
                    **metrics,
                }
            )
    by_month = pd.DataFrame(metrics_rows)
    summary = aggregate_metrics(by_month)
    return by_month, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prediction-paths",
        type=parse_csv_paths,
        default=parse_csv_paths(
            "experiments/20260629_073137_trade_overestimate_high_q75_expanding_min3_highcost_risk5/"
            "predictions_validation_oof_trade_overestimate_high_model.parquet,"
            "experiments/20260629_073137_trade_overestimate_high_q75_expanding_min3_highcost_risk5/"
            "predictions_apply_trade_overestimate_high_model.parquet,"
            "experiments/20260629_084211_trade_overestimate_high_q75_expanding_min3_highcost_risk5_apply_2025_06/"
            "predictions_apply_trade_overestimate_high_model.parquet"
        ),
    )
    parser.add_argument(
        "--threshold-predictions",
        type=parse_csv_paths,
        default=parse_csv_paths(
            "experiments/20260629_073137_trade_overestimate_high_q75_expanding_min3_highcost_risk5/"
            "predictions_validation_oof_trade_overestimate_high_model.parquet"
        ),
    )
    parser.add_argument("--months", default="2025-02,2025-03,2025-04,2025-05,2025-06")
    parser.add_argument("--threshold-months", default="2025-02,2025-03,2025-04")
    parser.add_argument("--threshold-quantiles", default="0.75,0.9")
    parser.add_argument("--caps", default="60,120,240")
    parser.add_argument("--side-modes", type=parse_side_modes, default=parse_side_modes("both"))
    parser.add_argument(
        "--include-combined-regimes",
        type=parse_optional_csv_strings,
        default=[],
        help="optional comma-separated combined_regime values where holding caps may trigger",
    )
    parser.add_argument(
        "--exclude-combined-regimes",
        type=parse_optional_csv_strings,
        default=[],
        help="optional comma-separated combined_regime values where holding caps must not trigger",
    )
    parser.add_argument(
        "--include-combined-session-pairs",
        type=parse_combined_session_pairs,
        default=[],
        help=(
            "optional comma-separated combined_regime:session_regime pairs where holding caps may trigger"
        ),
    )
    parser.add_argument(
        "--exclude-combined-session-pairs",
        type=parse_combined_session_pairs,
        default=[],
        help=(
            "optional comma-separated combined_regime:session_regime pairs where holding caps must not trigger"
        ),
    )
    parser.add_argument(
        "--exclude-combined-session-pairs-by-month",
        type=Path,
        default=None,
        help=(
            "optional CSV from holding_cap_context_walkforward with target_month, combined_regime, "
            "and session_regime columns"
        ),
    )
    parser.add_argument("--exclude-month-context-selection-scope", default="pooled")
    parser.add_argument("--exclude-month-context-scope", default="pooled")
    parser.add_argument("--data", type=Path, default=Path("data/processed/histdata/xauusd/xauusd_m1.parquet"))
    parser.add_argument("--label", default="holding_risk_overlay_2025_02_06")
    parser.add_argument("--modeling-output-dir", type=Path, default=Path("data/reports/modeling"))
    parser.add_argument("--backtest-output-dir", type=Path, default=Path("data/reports/backtests"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    months = parse_csv_strings(args.months)
    threshold_months = parse_csv_strings(args.threshold_months)
    threshold_quantiles = parse_csv_floats(args.threshold_quantiles)
    caps = parse_csv_floats(args.caps)
    exclude_combined_session_pairs_by_month = read_month_context_pairs(
        args.exclude_combined_session_pairs_by_month,
        selection_scope=args.exclude_month_context_selection_scope,
        scope=args.exclude_month_context_scope,
    )

    modeling_dir = make_run_dir(args.modeling_output_dir, args.label)
    backtest_dir = make_run_dir(args.backtest_output_dir, args.label)

    combined = read_filtered_predictions(args.prediction_paths, months)
    threshold_frame = read_filtered_predictions(args.threshold_predictions, threshold_months)
    scored, threshold_summary = add_holding_cap_columns(
        combined,
        threshold_frame=threshold_frame,
        threshold_quantiles=threshold_quantiles,
        caps=caps,
        side_modes=args.side_modes,
        include_combined_regimes=args.include_combined_regimes,
        exclude_combined_regimes=args.exclude_combined_regimes,
        include_combined_session_pairs=args.include_combined_session_pairs,
        exclude_combined_session_pairs=args.exclude_combined_session_pairs,
        exclude_combined_session_pairs_by_month=exclude_combined_session_pairs_by_month,
    )
    predictions_path = modeling_dir / "predictions_holding_overlay.parquet"
    scored.to_parquet(predictions_path, index=False)
    threshold_summary.to_csv(modeling_dir / "holding_threshold_summary.csv", index=False)

    by_month, summary = run_policy_grid(
        predictions_path=predictions_path,
        predictions=scored,
        months=months,
        data_path=args.data,
        backtest_dir=backtest_dir,
        threshold_quantiles=threshold_quantiles,
        caps=caps,
        side_modes=args.side_modes,
    )
    by_month.to_csv(modeling_dir / "policy_metrics_by_month.csv", index=False)
    summary.to_csv(modeling_dir / "policy_metrics_summary.csv", index=False)
    by_month.to_csv(backtest_dir / "policy_metrics_by_month.csv", index=False)
    summary.to_csv(backtest_dir / "policy_metrics_summary.csv", index=False)

    manifest = {
        "mode": "holding_risk_overlay",
        "prediction_paths": [str(path) for path in args.prediction_paths],
        "threshold_predictions": [str(path) for path in args.threshold_predictions],
        "predictions": str(predictions_path),
        "modeling_dir": str(modeling_dir),
        "backtest_dir": str(backtest_dir),
        "months": months,
        "threshold_months": threshold_months,
        "threshold_quantiles": threshold_quantiles,
        "caps": caps,
        "side_modes": args.side_modes,
        "include_combined_regimes": args.include_combined_regimes,
        "exclude_combined_regimes": args.exclude_combined_regimes,
        "include_combined_session_pairs": [
            f"{combined}:{session}" for combined, session in args.include_combined_session_pairs
        ],
        "exclude_combined_session_pairs": [
            f"{combined}:{session}" for combined, session in args.exclude_combined_session_pairs
        ],
        "exclude_combined_session_pairs_by_month_file": (
            str(args.exclude_combined_session_pairs_by_month)
            if args.exclude_combined_session_pairs_by_month is not None
            else None
        ),
        "exclude_month_context_selection_scope": args.exclude_month_context_selection_scope,
        "exclude_month_context_scope": args.exclude_month_context_scope,
        "exclude_combined_session_pairs_by_month": [
            f"{month}:{combined}:{session}"
            for month, combined, session in exclude_combined_session_pairs_by_month
        ],
        "stateful_prefix": STATEFUL_PREFIX,
        "risk_source": "pred_trade_failure_pred_hit_actual_miss_prob * pred_trade_overestimate_high_q75_prob",
        "policy": {
            "profit_multiplier": 1.0,
            "loss_multiplier": 1.2,
            "spread_points": 0.2,
            "slippage_points": 0.1,
            "execution_delay_bars": 1,
            "entry_threshold": 12.0,
            "short_entry_threshold_offset": 6.0,
            "side_margin": 5.0,
            "risk_penalties": [0.0, 5.0],
            "side_ev_penalty_rules": [
                "short:combined_regime=down_low_vol:5",
                "short:combined_regime=up_low_vol:10",
            ],
        },
        "policy_configs": [
            {"label": label, "config": serializable_policy_config(config)}
            for label, config in policy_configs(
                predictions_path,
                threshold_quantiles=threshold_quantiles,
                caps=caps,
                side_modes=args.side_modes,
            )
        ],
    }
    for path in (modeling_dir / "manifest.json", backtest_dir / "manifest.json"):
        with path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2, default=json_default)

    print("modeling_dir:", modeling_dir)
    print("backtest_dir:", backtest_dir)
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
