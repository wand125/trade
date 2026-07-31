#!/usr/bin/env python3
"""Diagnose repair options for negative months that already satisfy support targets."""

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

from trade_data.backtest import make_run_dir  # noqa: E402

from entry_ev_candidate_generation_gap_audit import parse_targets  # noqa: E402
from entry_ev_quantile_policy_backtest import policy_candidate_from_name  # noqa: E402
from entry_ev_thin_month_opposite_candidate_diagnostics import (  # noqa: E402
    SIDE_LABELS,
    build_side_rows,
    bool_series,
    local_json_default,
    mark_stateful_available,
    month_series,
    numeric_series,
    parquet_columns,
    parse_side_penalty_rules,
    read_current_trades,
)
from entry_ev_upstream_universe_coverage_diagnostics import (  # noqa: E402
    DEFAULT_CONFIG,
    filter_repair_targets,
    resolve_path,
    role_to_family,
    select_repair_row,
)


HORIZONS = (60, 240, 720)
DEFAULT_TARGETS = "refit2025_validation:2025-03:short"


def timestamp_key(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, utc=True, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def side_from_direction(value: Any) -> str:
    side = str(value).strip().lower()
    if side not in SIDE_LABELS:
        return ""
    return side


def best_horizon_from_values(row: pd.Series, *, prefix: str, suffix: str) -> tuple[int, float]:
    best_horizon = int(HORIZONS[0])
    best_value = -np.inf
    for horizon in HORIZONS:
        value = pd.to_numeric(pd.Series([row.get(f"{prefix}{horizon}{suffix}", np.nan)]), errors="coerce").iloc[0]
        if pd.notna(value) and float(value) > best_value:
            best_horizon = int(horizon)
            best_value = float(value)
    return best_horizon, best_value


def actual_at_horizon(row: pd.Series, *, horizon: int, prefix: str, suffix: str) -> float:
    value = pd.to_numeric(pd.Series([row.get(f"{prefix}{horizon}{suffix}", np.nan)]), errors="coerce").iloc[0]
    return float(value) if pd.notna(value) else np.nan


def add_current_trade_repair_columns(trades: pd.DataFrame) -> pd.DataFrame:
    output = trades.copy()
    output["trade_id"] = (
        output["role"].astype(str)
        + "|"
        + output["month"].astype(str).str.slice(0, 7)
        + "|"
        + output["direction"].astype(str)
        + "|"
        + timestamp_key(output["entry_decision_timestamp"])
    )
    adjusted = numeric_series(output, "adjusted_pnl", default=0.0)
    output["is_loss_trade"] = adjusted.lt(0.0)
    output["skip_trade_delta"] = -adjusted
    best_horizons: list[int] = []
    best_actuals: list[float] = []
    pred_horizons: list[int] = []
    pred_actuals: list[float] = []
    pred_values: list[float] = []
    for _, row in output.iterrows():
        best_horizon, best_actual = best_horizon_from_values(
            row,
            prefix="selected_fixed_",
            suffix="m_actual_pnl",
        )
        pred_horizon, pred_value = best_horizon_from_values(
            row,
            prefix="selected_fixed_",
            suffix="m_pred_pnl",
        )
        best_horizons.append(best_horizon)
        best_actuals.append(best_actual)
        pred_horizons.append(pred_horizon)
        pred_values.append(pred_value)
        pred_actuals.append(
            actual_at_horizon(
                row,
                horizon=pred_horizon,
                prefix="selected_fixed_",
                suffix="m_actual_pnl",
            )
        )
    output["fixed_best_horizon_minutes_oracle"] = best_horizons
    output["fixed_best_actual_pnl_oracle"] = best_actuals
    output["fixed_best_delta_vs_current_oracle"] = (
        numeric_series(output, "fixed_best_actual_pnl_oracle") - adjusted
    )
    output["pred_fixed_best_horizon_minutes"] = pred_horizons
    output["pred_fixed_best_pred_pnl"] = pred_values
    output["actual_at_pred_fixed_best_horizon"] = pred_actuals
    output["pred_fixed_best_delta_vs_current"] = (
        numeric_series(output, "actual_at_pred_fixed_best_horizon") - adjusted
    )
    for horizon in HORIZONS:
        pred_col = f"selected_fixed_{horizon}m_pred_pnl"
        actual_col = f"selected_fixed_{horizon}m_actual_pnl"
        output[f"fixed{horizon}_pred_minus_actual"] = (
            numeric_series(output, pred_col) - numeric_series(output, actual_col)
        )
    conditions = [
        output["is_loss_trade"] & output["fixed_best_delta_vs_current_oracle"].gt(0.0),
        output["is_loss_trade"] & output["skip_trade_delta"].gt(0.0),
        ~output["is_loss_trade"] & output["fixed_best_delta_vs_current_oracle"].gt(0.0),
    ]
    choices = [
        "loss_exit_horizon_oracle_improves",
        "loss_skip_or_replacement_only",
        "winner_exit_extension_oracle_improves",
    ]
    output["diagnostic_repair_class"] = np.select(
        conditions,
        choices,
        default="no_obvious_exit_repair",
    )
    return output


def strict_stage_checks(
    rows: pd.DataFrame,
    *,
    policy: Any,
    min_strict_side_margin: float,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "holding": bool_series(rows, "holding_ok", default=False),
            "score_floor": numeric_series(rows, "side_score", default=-np.inf).gt(policy.entry_threshold),
            "score_q": numeric_series(rows, "score_pct", default=-np.inf).ge(policy.score_quantile),
            "side_margin_q": numeric_series(rows, "side_margin_pct", default=-np.inf).ge(policy.side_gap_quantile),
            "rank_q": numeric_series(rows, "entry_rank_pct", default=-np.inf).ge(policy.rank_quantile),
            "side_margin": numeric_series(rows, "side_margin", default=-np.inf).ge(min_strict_side_margin),
        },
        index=rows.index,
    )


def add_candidate_gate_columns(rows: pd.DataFrame, *, config: dict[str, Any]) -> pd.DataFrame:
    output = rows.copy()
    policy = policy_candidate_from_name(config["candidate"])
    min_strict_side_margin = float(config.get("min_strict_side_margin", 0.0))
    output["strict_side_specific"] = (
        output["holding_ok"]
        & output["side_score"].gt(policy.entry_threshold)
        & output["score_pct"].ge(policy.score_quantile)
        & output["side_margin_pct"].ge(policy.side_gap_quantile)
        & output["entry_rank_pct"].ge(policy.rank_quantile)
        & output["side_margin"].ge(min_strict_side_margin)
    )
    output["relaxed_side_specific"] = (
        output["holding_ok"]
        & output["side_score"].gt(float(config.get("relaxed_min_score", 5.0)))
        & output["score_pct"].ge(float(config.get("relaxed_score_quantile", 0.90)))
        & output["side_margin_pct"].ge(float(config.get("relaxed_side_margin_quantile", 0.90)))
        & output["entry_rank_pct"].ge(float(config.get("relaxed_rank_quantile", 0.80)))
        & output["side_margin"].ge(float(config.get("relaxed_min_side_margin", 0.0)))
    )
    checks = strict_stage_checks(
        output,
        policy=policy,
        min_strict_side_margin=min_strict_side_margin,
    )
    output["strict_failed_stage_count"] = (~checks).sum(axis=1).astype(int)
    output["one_failed_strict_stage"] = output["strict_failed_stage_count"].eq(1)
    output["candidate_stage"] = np.select(
        [
            output["strict_side_specific"],
            output["relaxed_side_specific"],
            output["one_failed_strict_stage"],
        ],
        ["strict", "relaxed", "one_failed_strict_stage"],
        default="non_candidate",
    )
    return output


def add_side_pred_fixed_columns(side_rows: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    extras: list[pd.DataFrame] = []
    for side in SIDE_LABELS:
        extra = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    predictions["decision_timestamp"],
                    utc=True,
                    errors="coerce",
                ),
                "side": side,
            }
        )
        for horizon in HORIZONS:
            extra[f"side_pred_fixed_{horizon}m_adjusted_pnl"] = numeric_series(
                predictions,
                f"pred_{side}_fixed_{horizon}m_adjusted_pnl",
            )
        extras.append(extra)
    extra_frame = pd.concat(extras, ignore_index=True)
    return side_rows.merge(
        extra_frame,
        on=["decision_timestamp", "side"],
        how="left",
        validate="many_to_one",
    )


def add_candidate_horizon_columns(rows: pd.DataFrame) -> pd.DataFrame:
    output = rows.copy()
    pred_horizons: list[int] = []
    pred_values: list[float] = []
    actual_at_pred: list[float] = []
    actual_best_horizons: list[int] = []
    actual_best_values: list[float] = []
    for _, row in output.iterrows():
        pred_horizon, pred_value = best_horizon_from_values(
            row,
            prefix="side_pred_fixed_",
            suffix="m_adjusted_pnl",
        )
        actual_horizon, actual_value = best_horizon_from_values(
            row,
            prefix="side_fixed_",
            suffix="m_adjusted_pnl",
        )
        pred_horizons.append(pred_horizon)
        pred_values.append(pred_value)
        actual_at_pred.append(
            actual_at_horizon(
                row,
                horizon=pred_horizon,
                prefix="side_fixed_",
                suffix="m_adjusted_pnl",
            )
        )
        actual_best_horizons.append(actual_horizon)
        actual_best_values.append(actual_value)
    output["candidate_pred_fixed_best_horizon_minutes"] = pred_horizons
    output["candidate_pred_fixed_best_pred_pnl"] = pred_values
    output["candidate_actual_at_pred_fixed_best_horizon"] = actual_at_pred
    output["candidate_fixed_best_horizon_minutes_oracle"] = actual_best_horizons
    output["candidate_fixed_best_actual_pnl_oracle"] = actual_best_values
    return output


def load_extended_side_rows(
    *,
    prediction_path: Path,
    family: str,
    month: str,
    config: dict[str, Any],
) -> pd.DataFrame:
    side_penalty_rules = parse_side_penalty_rules(config.get("side_ev_penalty_rules", ""))
    needed_columns = [
        "decision_timestamp",
        "entry_timestamp",
        "dataset_month",
        "month",
        "combined_regime",
        "session_regime",
        config["long_column"],
        config["short_column"],
        config.get("long_holding_column", "pred_mlp_long_exit_event_minutes"),
        config.get("short_holding_column", "pred_mlp_short_exit_event_minutes"),
        "pred_long_entry_local_rank",
        "pred_short_entry_local_rank",
        "long_best_adjusted_pnl",
        "short_best_adjusted_pnl",
        "long_best_holding_minutes",
        "short_best_holding_minutes",
        "long_fixed_60m_adjusted_pnl",
        "short_fixed_60m_adjusted_pnl",
        "long_fixed_240m_adjusted_pnl",
        "short_fixed_240m_adjusted_pnl",
        "long_fixed_720m_adjusted_pnl",
        "short_fixed_720m_adjusted_pnl",
        "pred_long_fixed_60m_adjusted_pnl",
        "pred_short_fixed_60m_adjusted_pnl",
        "pred_long_fixed_240m_adjusted_pnl",
        "pred_short_fixed_240m_adjusted_pnl",
        "pred_long_fixed_720m_adjusted_pnl",
        "pred_short_fixed_720m_adjusted_pnl",
        *[rule[1] for rule in side_penalty_rules],
    ]
    columns = parquet_columns(prediction_path)
    read_columns = [column for column in dict.fromkeys(needed_columns) if column in columns]
    predictions = pd.read_parquet(prediction_path, columns=read_columns)
    predictions["month"] = month_series(predictions)
    predictions = predictions[predictions["month"].eq(month)].copy()
    if predictions.empty:
        return pd.DataFrame()
    side_rows = build_side_rows(
        predictions,
        family=family,
        long_column=config["long_column"],
        short_column=config["short_column"],
        long_holding_column=config.get("long_holding_column", "pred_mlp_long_exit_event_minutes"),
        short_holding_column=config.get("short_holding_column", "pred_mlp_short_exit_event_minutes"),
        min_valid_predicted_hold_minutes=float(config.get("min_valid_predicted_hold_minutes", 30.0)),
        max_predicted_hold_minutes=float(config.get("max_predicted_hold_minutes", 720.0)),
        side_penalty_rules=side_penalty_rules,
    )
    side_rows = add_side_pred_fixed_columns(side_rows, predictions)
    side_rows = add_candidate_gate_columns(side_rows, config=config)
    side_rows = add_candidate_horizon_columns(side_rows)
    side_rows["entry_key"] = timestamp_key(side_rows["decision_timestamp"]) + "|" + side_rows["side"].astype(str)
    return side_rows


def trade_intervals(trades: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for _, row in trades.iterrows():
        start = pd.to_datetime(row["entry_decision_timestamp"], utc=True, errors="coerce")
        end = pd.to_datetime(row["exit_decision_timestamp"], utc=True, errors="coerce")
        if pd.isna(start) or pd.isna(end):
            continue
        if end <= start:
            end = start + pd.Timedelta(minutes=1)
        intervals.append((start, end))
    return sorted(intervals)


def intervals_without_trade(
    trades: pd.DataFrame,
    *,
    trade_id: str,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    subset = trades[trades["trade_id"].astype(str).ne(trade_id)]
    return trade_intervals(subset)


def current_entry_keys(trades: pd.DataFrame) -> set[str]:
    timestamps = timestamp_key(trades["entry_decision_timestamp"])
    sides = trades["direction"].map(side_from_direction)
    return set((timestamps + "|" + sides).dropna().astype(str).tolist())


def candidate_pool_for_loss(
    *,
    side_rows: pd.DataFrame,
    current_trades: pd.DataFrame,
    loss_trade: pd.Series,
    include_non_candidate_top_score: bool,
) -> pd.DataFrame:
    intervals = intervals_without_trade(current_trades, trade_id=str(loss_trade["trade_id"]))
    rows = mark_stateful_available(side_rows, intervals)
    rows = rows[bool_series(rows, "stateful_available")].copy()
    rows = rows[~rows["entry_key"].isin(current_entry_keys(current_trades))].copy()
    if not include_non_candidate_top_score:
        rows = rows[rows["candidate_stage"].astype(str).ne("non_candidate")].copy()
    rows["loss_trade_id"] = str(loss_trade["trade_id"])
    rows["loss_trade_direction"] = str(loss_trade["direction"])
    rows["loss_trade_adjusted_pnl"] = float(loss_trade["adjusted_pnl"])
    rows["replacement_delta_pred_fixed_horizon"] = (
        numeric_series(rows, "candidate_actual_at_pred_fixed_best_horizon")
        - float(loss_trade["adjusted_pnl"])
    )
    rows["replacement_delta_oracle_fixed_best"] = (
        numeric_series(rows, "candidate_fixed_best_actual_pnl_oracle")
        - float(loss_trade["adjusted_pnl"])
    )
    return rows


def summarize_loss_replacement_pool(
    *,
    month_pnl: float,
    loss_trade: pd.Series,
    pool: pd.DataFrame,
) -> dict[str, Any]:
    base = {
        "loss_trade_id": str(loss_trade["trade_id"]),
        "loss_trade_direction": str(loss_trade["direction"]),
        "loss_trade_entry_decision_timestamp": str(loss_trade["entry_decision_timestamp"]),
        "loss_trade_adjusted_pnl": float(loss_trade["adjusted_pnl"]),
        "candidate_rows": int(len(pool)),
        "strict_rows": int(pool["candidate_stage"].astype(str).eq("strict").sum()) if not pool.empty else 0,
        "relaxed_rows": int(pool["candidate_stage"].astype(str).eq("relaxed").sum()) if not pool.empty else 0,
        "onefail_rows": int(pool["candidate_stage"].astype(str).eq("one_failed_strict_stage").sum()) if not pool.empty else 0,
    }
    if pool.empty:
        return {
            **base,
            "top_score_side": "",
            "top_score_timestamp": "",
            "top_score_stage": "",
            "top_score_side_score": np.nan,
            "top_score_pred_horizon": 0,
            "top_score_actual_at_pred_horizon": np.nan,
            "top_score_month_pnl_at_pred_horizon": np.nan,
            "oracle_best_candidate_side": "",
            "oracle_best_candidate_timestamp": "",
            "oracle_best_candidate_actual": np.nan,
            "oracle_best_month_pnl": np.nan,
        }
    top_score = pool.sort_values(
        ["side_score", "score_pct", "side_margin_pct", "entry_rank_pct"],
        ascending=[False, False, False, False],
    ).iloc[0]
    oracle = pool.sort_values(
        ["candidate_fixed_best_actual_pnl_oracle", "side_score"],
        ascending=[False, False],
    ).iloc[0]
    return {
        **base,
        "top_score_side": str(top_score["side"]),
        "top_score_timestamp": str(top_score["decision_timestamp"]),
        "top_score_stage": str(top_score["candidate_stage"]),
        "top_score_side_score": float(top_score["side_score"]),
        "top_score_pred_horizon": int(top_score["candidate_pred_fixed_best_horizon_minutes"]),
        "top_score_actual_at_pred_horizon": float(top_score["candidate_actual_at_pred_fixed_best_horizon"]),
        "top_score_month_pnl_at_pred_horizon": float(
            month_pnl - float(loss_trade["adjusted_pnl"]) + float(top_score["candidate_actual_at_pred_fixed_best_horizon"])
        ),
        "oracle_best_candidate_side": str(oracle["side"]),
        "oracle_best_candidate_timestamp": str(oracle["decision_timestamp"]),
        "oracle_best_candidate_actual": float(oracle["candidate_fixed_best_actual_pnl_oracle"]),
        "oracle_best_month_pnl": float(
            month_pnl - float(loss_trade["adjusted_pnl"]) + float(oracle["candidate_fixed_best_actual_pnl_oracle"])
        ),
    }


def build_month_summary(
    *,
    role: str,
    family: str,
    month: str,
    repair_row: pd.Series | None,
    trade_diag: pd.DataFrame,
    replacement_summary: pd.DataFrame,
) -> dict[str, Any]:
    month_pnl = float(numeric_series(trade_diag, "adjusted_pnl", default=0.0).sum())
    losses = trade_diag[bool_series(trade_diag, "is_loss_trade")]
    best_exit_delta = float(numeric_series(losses, "fixed_best_delta_vs_current_oracle", default=0.0).max()) if not losses.empty else 0.0
    best_pred_exit_delta = float(numeric_series(losses, "pred_fixed_best_delta_vs_current", default=0.0).max()) if not losses.empty else 0.0
    best_topscore_month = (
        float(numeric_series(replacement_summary, "top_score_month_pnl_at_pred_horizon").max())
        if not replacement_summary.empty
        else np.nan
    )
    best_oracle_replacement_month = (
        float(numeric_series(replacement_summary, "oracle_best_month_pnl").max())
        if not replacement_summary.empty
        else np.nan
    )
    return {
        "role": role,
        "family": family,
        "month": month,
        "repair_target_present": repair_row is not None,
        "extra_long_needed": int(repair_row.get("extra_long_needed", 0)) if repair_row is not None else 0,
        "extra_short_needed": int(repair_row.get("extra_short_needed", 0)) if repair_row is not None else 0,
        "support_sufficient_negative_month": bool(
            repair_row is not None
            and month_pnl < 0.0
            and int(repair_row.get("extra_long_needed", 0)) == 0
            and int(repair_row.get("extra_short_needed", 0)) == 0
        ),
        "month_pnl": month_pnl,
        "trade_count": int(len(trade_diag)),
        "long_trade_count": int(trade_diag["direction"].astype(str).eq("long").sum()),
        "short_trade_count": int(trade_diag["direction"].astype(str).eq("short").sum()),
        "loss_trade_count": int(len(losses)),
        "loss_pnl_sum": float(numeric_series(losses, "adjusted_pnl", default=0.0).sum()),
        "winner_pnl_sum": float(numeric_series(trade_diag[~bool_series(trade_diag, "is_loss_trade")], "adjusted_pnl", default=0.0).sum()),
        "skip_all_loss_trades_month_pnl_oracle": float(month_pnl - numeric_series(losses, "adjusted_pnl", default=0.0).sum()),
        "best_single_skip_month_pnl_oracle": float(month_pnl - numeric_series(losses, "adjusted_pnl", default=0.0).min()) if not losses.empty else month_pnl,
        "best_single_exit_fixed_month_pnl_oracle": float(month_pnl + best_exit_delta),
        "best_single_pred_fixed_exit_month_pnl": float(month_pnl + best_pred_exit_delta),
        "best_topscore_replacement_month_pnl": best_topscore_month,
        "best_oracle_replacement_month_pnl": best_oracle_replacement_month,
    }


def run_diagnostics(args: argparse.Namespace) -> Path:
    config_path = resolve_path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    repair_targets_path = resolve_path(config["repair_targets"])
    current_trades_path = resolve_path(config["current_trades"])
    family_predictions = {
        str(family): resolve_path(path)
        for family, path in dict(config["family_predictions"]).items()
    }
    repair_targets = filter_repair_targets(
        pd.read_csv(repair_targets_path),
        candidate=config["candidate"],
        variant_contains=config.get("variant_contains", ""),
        entry_block_rule=config.get("entry_block_rule", ""),
    )
    current = read_current_trades(
        current_trades_path,
        candidate=config["candidate"],
        selector_variant_contains=config.get("selector_variant_contains", ""),
        entry_block_rule=config.get("entry_block_rule", ""),
    )

    target_rows = []
    trade_rows = []
    replacement_summary_rows = []
    replacement_example_rows = []
    for role, month, _side in parse_targets(args.targets):
        family = role_to_family(role)
        repair_row = select_repair_row(repair_targets, role=role, month=month)
        if repair_row is not None:
            family = str(repair_row.get("family", family))
        current_target = current[
            current["role"].astype(str).eq(role)
            & current["family"].astype(str).eq(family)
            & current["month"].astype(str).eq(month)
        ].copy()
        if current_target.empty:
            continue
        current_target = add_current_trade_repair_columns(current_target)
        trade_rows.append(current_target)
        prediction_path = family_predictions.get(family)
        if prediction_path is None:
            raise ValueError(f"missing prediction path for family {family}")
        side_rows = load_extended_side_rows(
            prediction_path=prediction_path,
            family=family,
            month=month,
            config=config,
        )
        month_pnl = float(numeric_series(current_target, "adjusted_pnl", default=0.0).sum())
        loss_trades = current_target[bool_series(current_target, "is_loss_trade")].copy()
        target_replacement_summary_rows: list[dict[str, Any]] = []
        for _, loss_trade in loss_trades.iterrows():
            pool = candidate_pool_for_loss(
                side_rows=side_rows,
                current_trades=current_target,
                loss_trade=loss_trade,
                include_non_candidate_top_score=args.include_non_candidate_top_score,
            )
            replacement_summary_rows.append(
                summarize_loss_replacement_pool(
                    month_pnl=month_pnl,
                    loss_trade=loss_trade,
                    pool=pool,
                )
            )
            target_replacement_summary_rows.append(replacement_summary_rows[-1])
            if not pool.empty:
                examples = pool.sort_values(
                    ["side_score", "score_pct", "side_margin_pct", "entry_rank_pct"],
                    ascending=[False, False, False, False],
                ).head(int(args.example_rows)).copy()
                replacement_example_rows.append(examples)
        target_rows.append(
            build_month_summary(
                role=role,
                family=family,
                month=month,
                repair_row=repair_row,
                trade_diag=current_target,
                replacement_summary=pd.DataFrame(target_replacement_summary_rows),
            )
        )

    month_summary = pd.DataFrame(target_rows)
    trade_diag = pd.concat(trade_rows, ignore_index=True) if trade_rows else pd.DataFrame()
    replacement_summary = (
        pd.DataFrame(replacement_summary_rows)
        if replacement_summary_rows
        else pd.DataFrame()
    )
    replacement_examples = (
        pd.concat(replacement_example_rows, ignore_index=True)
        if replacement_example_rows
        else pd.DataFrame()
    )

    run_dir = make_run_dir(resolve_path(args.output_root), args.run_label)
    month_summary.to_csv(run_dir / "support_sufficient_month_summary.csv", index=False)
    trade_diag.to_csv(run_dir / "support_sufficient_current_trade_diagnostics.csv", index=False)
    replacement_summary.to_csv(run_dir / "support_sufficient_loss_replacement_summary.csv", index=False)
    replacement_examples.to_csv(run_dir / "support_sufficient_replacement_candidate_examples.csv", index=False)
    meta = {
        "config": config_path,
        "repair_targets": repair_targets_path,
        "current_trades": current_trades_path,
        "targets": parse_targets(args.targets),
        "include_non_candidate_top_score": args.include_non_candidate_top_score,
        "example_rows": args.example_rows,
        "config_values": config,
    }
    (run_dir / "support_sufficient_repair_meta.json").write_text(
        json.dumps(meta, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Support-sufficient negative month summary:")
    print(month_summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/reports/backtests")
    parser.add_argument("--run-label", default="entry_ev_support_sufficient_negative_month_repair_diagnostics")
    parser.add_argument("--example-rows", type=int, default=20)
    parser.add_argument(
        "--include-non-candidate-top-score",
        action="store_true",
        help="Include statefully available holding-ok rows even when strict/relaxed/one-fail gates fail.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
