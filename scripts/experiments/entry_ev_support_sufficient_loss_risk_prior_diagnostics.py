#!/usr/bin/env python3
"""Diagnose prior-observable loss risk for support-sufficient negative months."""

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
for path in (SRC, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from trade_data.backtest import make_run_dir  # noqa: E402

from entry_ev_candidate_generation_gap_audit import parse_targets  # noqa: E402
from entry_ev_thin_month_opposite_candidate_diagnostics import (  # noqa: E402
    bool_series,
    local_json_default,
    numeric_series,
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
DEFAULT_CONTEXT_SPECS = (
    "direction;"
    "direction,session_regime;"
    "direction,combined_regime;"
    "direction,combined_regime,session_regime;"
    "direction,combined_regime,session_regime,entry_hour"
)


def parse_context_specs(value: str) -> list[list[str]]:
    specs: list[list[str]] = []
    for item in str(value).split(";"):
        columns = [column.strip() for column in item.split(",") if column.strip()]
        if columns:
            specs.append(columns)
    if not specs:
        raise ValueError("at least one context spec is required")
    return specs


def context_spec_name(columns: list[str]) -> str:
    return ",".join(columns) if columns else "all"


def timestamp_key(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, utc=True, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def context_key(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    if not columns:
        return pd.Series("all", index=frame.index, dtype="string")
    available = [column for column in columns if column in frame.columns]
    if not available:
        return pd.Series("missing", index=frame.index, dtype="string")
    return frame[available].fillna("missing").astype(str).agg("|".join, axis=1)


def bucket_series(
    values: pd.Series,
    *,
    bins: list[float],
    labels: list[str],
    missing_label: str = "missing",
) -> pd.Series:
    bucketed = pd.cut(pd.to_numeric(values, errors="coerce"), bins=bins, labels=labels, include_lowest=True)
    return bucketed.astype("object").where(bucketed.notna(), missing_label).astype(str)


def best_horizon(row: pd.Series, *, prefix: str, suffix: str) -> tuple[int, float]:
    best = int(HORIZONS[0])
    value = -np.inf
    for horizon in HORIZONS:
        column = f"{prefix}{horizon}{suffix}"
        current = pd.to_numeric(pd.Series([row.get(column, np.nan)]), errors="coerce").iloc[0]
        if pd.notna(current) and float(current) > value:
            best = int(horizon)
            value = float(current)
    return best, value


def actual_at_predicted_horizon(row: pd.Series, horizon: int) -> float:
    column = f"selected_fixed_{horizon}m_actual_pnl"
    value = pd.to_numeric(pd.Series([row.get(column, np.nan)]), errors="coerce").iloc[0]
    return float(value) if pd.notna(value) else np.nan


def add_observable_trade_features(
    trades: pd.DataFrame,
    *,
    large_loss_threshold: float,
) -> pd.DataFrame:
    output = trades.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["entry_decision_timestamp"] = pd.to_datetime(
        output["entry_decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output = output.sort_values(["entry_decision_timestamp", "role", "direction"]).reset_index(drop=True)
    output["trade_id"] = (
        output["role"].astype(str)
        + "|"
        + output["month"].astype(str)
        + "|"
        + output["direction"].astype(str)
        + "|"
        + timestamp_key(output["entry_decision_timestamp"])
    )

    output["adjusted_pnl_num"] = numeric_series(output, "adjusted_pnl", default=0.0)
    output["is_loss_trade"] = output["adjusted_pnl_num"].lt(0.0)
    output["is_large_loss_trade"] = output["adjusted_pnl_num"].le(float(large_loss_threshold))
    output["loss_first_prob"] = numeric_series(output, "selected_loss_first_prob")
    output["taken_ev"] = numeric_series(output, "pred_taken_ev")
    output["opposite_ev"] = numeric_series(output, "pred_opposite_ev")
    output["side_confidence_gap"] = numeric_series(output, "pred_side_confidence_gap")
    output["entry_local_rank"] = numeric_series(output, "pred_taken_entry_local_rank")
    output["entry_hour_num"] = numeric_series(output, "entry_hour", default=np.nan)

    pred_horizons: list[int] = []
    pred_values: list[float] = []
    pred_actuals: list[float] = []
    for _, row in output.iterrows():
        horizon, value = best_horizon(row, prefix="selected_fixed_", suffix="m_pred_pnl")
        pred_horizons.append(horizon)
        pred_values.append(value)
        pred_actuals.append(actual_at_predicted_horizon(row, horizon))
    output["pred_fixed_best_horizon_minutes"] = pred_horizons
    output["pred_fixed_best_pred_pnl"] = pred_values
    output["actual_at_pred_fixed_best_horizon"] = pred_actuals
    pred_columns = [f"selected_fixed_{horizon}m_pred_pnl" for horizon in HORIZONS]
    for column in pred_columns:
        output[column] = numeric_series(output, column)
    output["pred_fixed_dispersion"] = output[pred_columns].max(axis=1) - output[pred_columns].min(axis=1)
    output["pred_fixed_best_minus_taken_ev"] = output["pred_fixed_best_pred_pnl"] - output["taken_ev"]
    output["pred_ev_error"] = output["taken_ev"] - output["adjusted_pnl_num"]

    output["loss_first_bucket"] = bucket_series(
        output["loss_first_prob"],
        bins=[-np.inf, 0.20, 0.30, 0.40, 0.50, np.inf],
        labels=["lt0p20", "0p20_0p30", "0p30_0p40", "0p40_0p50", "ge0p50"],
    )
    output["taken_ev_bucket"] = bucket_series(
        output["taken_ev"],
        bins=[-np.inf, 0.0, 2.0, 5.0, 8.0, np.inf],
        labels=["lt0", "0_2", "2_5", "5_8", "ge8"],
    )
    output["side_gap_bucket"] = bucket_series(
        output["side_confidence_gap"],
        bins=[-np.inf, 0.0, 0.05, 0.15, 0.30, np.inf],
        labels=["lt0", "0_0p05", "0p05_0p15", "0p15_0p30", "ge0p30"],
    )
    output["entry_rank_bucket"] = bucket_series(
        output["entry_local_rank"],
        bins=[-np.inf, 0.50, 0.60, 0.80, np.inf],
        labels=["lt0p50", "0p50_0p60", "0p60_0p80", "ge0p80"],
    )
    output["pred_fixed_best_bucket"] = bucket_series(
        output["pred_fixed_best_pred_pnl"],
        bins=[-np.inf, 0.0, 2.0, 5.0, 8.0, np.inf],
        labels=["lt0", "0_2", "2_5", "5_8", "ge8"],
    )
    output["pred_fixed_horizon_bucket"] = output["pred_fixed_best_horizon_minutes"].astype(str) + "m"
    return output


def prior_metric_row(
    frame: pd.DataFrame,
    *,
    large_loss_threshold: float,
) -> dict[str, Any]:
    pnl = numeric_series(frame, "adjusted_pnl_num", default=0.0)
    count = int(len(frame))
    losses = pnl.lt(0.0)
    large_losses = pnl.le(float(large_loss_threshold))
    return {
        "prior_count": count,
        "prior_month_count": int(frame["month"].astype(str).nunique()) if count else 0,
        "prior_loss_count": int(losses.sum()),
        "prior_large_loss_count": int(large_losses.sum()),
        "prior_winner_count": int(pnl.gt(0.0).sum()),
        "prior_pnl_sum": float(pnl.sum()) if count else 0.0,
        "prior_pnl_mean": float(pnl.mean()) if count else np.nan,
        "prior_loss_rate": float(losses.mean()) if count else np.nan,
        "prior_large_loss_rate": float(large_losses.mean()) if count else np.nan,
        "prior_min_pnl": float(pnl.min()) if count else np.nan,
        "prior_max_pnl": float(pnl.max()) if count else np.nan,
    }


def build_prior_context_rows(
    trades: pd.DataFrame,
    focus: pd.DataFrame,
    *,
    context_specs: list[list[str]],
    large_loss_threshold: float,
) -> pd.DataFrame:
    if focus.empty:
        return pd.DataFrame()
    all_trades = trades.copy()
    all_trades["entry_decision_timestamp"] = pd.to_datetime(
        all_trades["entry_decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    all_trades = all_trades.sort_values("entry_decision_timestamp").reset_index(drop=True)

    rows: list[dict[str, Any]] = []
    for _, target in focus.iterrows():
        entry_time = pd.to_datetime(target["entry_decision_timestamp"], utc=True, errors="coerce")
        prior_all = all_trades[all_trades["entry_decision_timestamp"].lt(entry_time)].copy()
        for columns in context_specs:
            available = [column for column in columns if column in all_trades.columns]
            spec = context_spec_name(available)
            if available:
                mask = pd.Series(True, index=prior_all.index)
                key_parts: list[str] = []
                for column in available:
                    value = str(target.get(column, "missing"))
                    key_parts.append(value)
                    mask &= prior_all[column].fillna("missing").astype(str).eq(value)
                prior = prior_all[mask]
                key = "|".join(key_parts)
            else:
                prior = prior_all
                key = "all"
            rows.append(
                {
                    "trade_id": str(target["trade_id"]),
                    "role": str(target.get("role", "")),
                    "family": str(target.get("family", "")),
                    "month": str(target.get("month", ""))[:7],
                    "direction": str(target.get("direction", "")),
                    "entry_decision_timestamp": target["entry_decision_timestamp"],
                    "adjusted_pnl": float(target.get("adjusted_pnl_num", np.nan)),
                    "is_loss_trade": bool(target.get("is_loss_trade", False)),
                    "is_large_loss_trade": bool(target.get("is_large_loss_trade", False)),
                    "context_spec": spec,
                    "context_key": key,
                    **prior_metric_row(prior, large_loss_threshold=large_loss_threshold),
                }
            )
    return pd.DataFrame(rows)


def feature_rule_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    loss_first = numeric_series(frame, "loss_first_prob")
    taken_ev = numeric_series(frame, "taken_ev")
    pred_best = numeric_series(frame, "pred_fixed_best_pred_pnl")
    side_gap = numeric_series(frame, "side_confidence_gap")
    horizon = numeric_series(frame, "pred_fixed_best_horizon_minutes", default=0.0)
    return {
        "loss_first_ge0p30": loss_first.ge(0.30),
        "loss_first_ge0p40": loss_first.ge(0.40),
        "ev_ge5_lossfirst_lt0p30": taken_ev.ge(5.0) & loss_first.lt(0.30),
        "fixed_best_ge5_lossfirst_lt0p30": pred_best.ge(5.0) & loss_first.lt(0.30),
        "pred_fixed_horizon_720": horizon.eq(720.0),
        "pred_fixed_best_ge5": pred_best.ge(5.0),
        "side_gap_ge0p15_lossfirst_lt0p30": side_gap.ge(0.15) & loss_first.lt(0.30),
        "lossfirst_ge0p40_or_ev_ge5_lossfirst_lt0p30": loss_first.ge(0.40)
        | (taken_ev.ge(5.0) & loss_first.lt(0.30)),
    }


def prior_rule_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    count = numeric_series(frame, "prior_count", default=0.0)
    loss_rate = numeric_series(frame, "prior_loss_rate")
    large_loss_rate = numeric_series(frame, "prior_large_loss_rate")
    mean_pnl = numeric_series(frame, "prior_pnl_mean")
    total_pnl = numeric_series(frame, "prior_pnl_sum", default=0.0)
    return {
        "prior_count_ge3_lossrate_ge0p60": count.ge(3.0) & loss_rate.ge(0.60),
        "prior_count_ge3_mean_pnl_lt0": count.ge(3.0) & mean_pnl.lt(0.0),
        "prior_count_ge5_lossrate_ge0p50": count.ge(5.0) & loss_rate.ge(0.50),
        "prior_count_ge5_total_pnl_lt0": count.ge(5.0) & total_pnl.lt(0.0),
        "prior_count_ge3_large_lossrate_ge0p25": count.ge(3.0) & large_loss_rate.ge(0.25),
    }


def rule_catalog(context_specs: list[list[str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    empty = pd.DataFrame(index=[0])
    for rule in feature_rule_masks(empty):
        rows.append({"rule": rule, "rule_family": "feature", "context_spec": "feature"})
    for columns in context_specs:
        spec = context_spec_name(columns)
        for rule in prior_rule_masks(pd.DataFrame(index=[0])):
            rows.append({"rule": rule, "rule_family": "prior_context", "context_spec": spec})
    return pd.DataFrame(rows)


def build_rule_hits(trades: pd.DataFrame, prior_context: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for rule, mask in feature_rule_masks(trades).items():
        hit = trades.loc[mask.fillna(False)].copy()
        if hit.empty:
            continue
        hit["rule"] = rule
        hit["rule_family"] = "feature"
        hit["context_spec"] = "feature"
        hit["context_key"] = ""
        rows.append(hit)
    if not prior_context.empty:
        for rule, mask in prior_rule_masks(prior_context).items():
            hit = prior_context.loc[mask.fillna(False)].copy()
            if hit.empty:
                continue
            hit["rule"] = rule
            hit["rule_family"] = "prior_context"
            rows.append(hit)
    if not rows:
        return pd.DataFrame(
            columns=[
                "trade_id",
                "rule",
                "rule_family",
                "context_spec",
                "context_key",
                "adjusted_pnl",
                "is_loss_trade",
                "is_large_loss_trade",
            ]
        )
    return pd.concat(rows, ignore_index=True, sort=False)


def summarize_rule_frame(frame: pd.DataFrame, *, total_loss_count: int) -> dict[str, Any]:
    if frame.empty:
        return {
            "flagged_trade_count": 0,
            "flagged_loss_count": 0,
            "flagged_large_loss_count": 0,
            "flagged_winner_count": 0,
            "flagged_pnl": 0.0,
            "flagged_loss_pnl": 0.0,
            "flagged_winner_pnl": 0.0,
            "flagged_loss_rate": np.nan,
            "loss_recall": 0.0,
            "block_delta_if_removed": 0.0,
        }
    pnl = numeric_series(frame, "adjusted_pnl_num", default=np.nan)
    if pnl.isna().all() and "adjusted_pnl" in frame.columns:
        pnl = numeric_series(frame, "adjusted_pnl", default=0.0)
    is_loss = bool_series(frame, "is_loss_trade", default=False)
    is_large_loss = bool_series(frame, "is_large_loss_trade", default=False)
    flagged_count = int(len(frame))
    loss_count = int(is_loss.sum())
    winner = ~is_loss
    return {
        "flagged_trade_count": flagged_count,
        "flagged_loss_count": loss_count,
        "flagged_large_loss_count": int(is_large_loss.sum()),
        "flagged_winner_count": int(winner.sum()),
        "flagged_pnl": float(pnl.sum()),
        "flagged_loss_pnl": float(pnl[is_loss].sum()) if loss_count else 0.0,
        "flagged_winner_pnl": float(pnl[winner].sum()) if winner.any() else 0.0,
        "flagged_loss_rate": float(loss_count / flagged_count) if flagged_count else np.nan,
        "loss_recall": float(loss_count / total_loss_count) if total_loss_count else 0.0,
        "block_delta_if_removed": float(-pnl.sum()),
    }


def summarize_rule_hits(
    hits: pd.DataFrame,
    trades: pd.DataFrame,
    *,
    target_trade_ids: set[str],
    catalog: pd.DataFrame,
) -> pd.DataFrame:
    trade_index = trades.drop_duplicates("trade_id").set_index("trade_id", drop=False)
    total_loss_count = int(bool_series(trades, "is_loss_trade").sum())
    target = trades[trades["trade_id"].astype(str).isin(target_trade_ids)].copy()
    target_loss_count = int(bool_series(target, "is_loss_trade").sum())
    rows: list[dict[str, Any]] = []
    for _, rule_row in catalog.iterrows():
        rule = str(rule_row["rule"])
        context_spec = str(rule_row["context_spec"])
        scoped = hits[
            hits["rule"].astype(str).eq(rule)
            & hits["context_spec"].astype(str).eq(context_spec)
        ].copy()
        ids = scoped["trade_id"].astype(str).drop_duplicates().tolist() if not scoped.empty else []
        flagged = trade_index.loc[trade_index.index.intersection(ids)].copy()
        target_flagged = flagged[flagged["trade_id"].astype(str).isin(target_trade_ids)].copy()
        rows.append(
            {
                "rule": rule,
                "rule_family": str(rule_row["rule_family"]),
                "context_spec": context_spec,
                "evaluated_trade_count": int(len(trades)),
                "evaluated_loss_count": total_loss_count,
                **summarize_rule_frame(flagged, total_loss_count=total_loss_count),
                "target_trade_count": int(len(target)),
                "target_loss_count": target_loss_count,
                **{
                    f"target_{key}": value
                    for key, value in summarize_rule_frame(
                        target_flagged,
                        total_loss_count=target_loss_count,
                    ).items()
                },
            }
        )
    return pd.DataFrame(rows).sort_values(
        [
            "target_loss_recall",
            "target_block_delta_if_removed",
            "loss_recall",
            "block_delta_if_removed",
        ],
        ascending=[False, False, False, False],
    )


def add_target_hit_counts(target: pd.DataFrame, hits: pd.DataFrame) -> pd.DataFrame:
    output = target.copy()
    if hits.empty:
        output["risk_rule_hit_count"] = 0
        output["feature_rule_hit_count"] = 0
        output["prior_rule_hit_count"] = 0
        output["risk_rules"] = ""
        return output
    grouped = (
        hits.groupby("trade_id")
        .agg(
            risk_rule_hit_count=("rule", "count"),
            feature_rule_hit_count=("rule_family", lambda values: int((values == "feature").sum())),
            prior_rule_hit_count=("rule_family", lambda values: int((values == "prior_context").sum())),
            risk_rules=("rule", lambda values: ";".join(sorted(set(map(str, values))))),
        )
        .reset_index()
    )
    output = output.merge(grouped, on="trade_id", how="left")
    for column in ["risk_rule_hit_count", "feature_rule_hit_count", "prior_rule_hit_count"]:
        output[column] = numeric_series(output, column, default=0.0).astype(int)
    output["risk_rules"] = output["risk_rules"].fillna("")
    return output


def run_diagnostics(args: argparse.Namespace) -> Path:
    config_path = resolve_path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    repair_targets_path = resolve_path(config["repair_targets"])
    current_trades_path = resolve_path(config["current_trades"])
    context_specs = parse_context_specs(args.context_specs)

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
    trades = add_observable_trade_features(
        current,
        large_loss_threshold=float(args.large_loss_threshold),
    )

    target_trade_frames: list[pd.DataFrame] = []
    month_summary_rows: list[dict[str, Any]] = []
    for role, month, side in parse_targets(args.targets):
        family = role_to_family(role)
        repair_row = select_repair_row(repair_targets, role=role, month=month)
        if repair_row is not None:
            family = str(repair_row.get("family", family))
        target = trades[
            trades["role"].astype(str).eq(role)
            & trades["family"].astype(str).eq(family)
            & trades["month"].astype(str).eq(month)
        ].copy()
        target["target_side"] = side
        month_pnl = float(numeric_series(target, "adjusted_pnl_num", default=0.0).sum())
        loss_count = int(bool_series(target, "is_loss_trade").sum())
        support_sufficient = bool(
            repair_row is not None
            and month_pnl < 0.0
            and int(repair_row.get("extra_long_needed", 0)) == 0
            and int(repair_row.get("extra_short_needed", 0)) == 0
        )
        target["support_sufficient_negative_month"] = support_sufficient
        target_trade_frames.append(target)
        month_summary_rows.append(
            {
                "role": role,
                "family": family,
                "month": month,
                "target_side": side,
                "support_sufficient_negative_month": support_sufficient,
                "month_pnl": month_pnl,
                "trade_count": int(len(target)),
                "loss_trade_count": loss_count,
                "large_loss_trade_count": int(bool_series(target, "is_large_loss_trade").sum()),
                "winner_pnl_sum": float(
                    numeric_series(target[~bool_series(target, "is_loss_trade")], "adjusted_pnl_num", default=0.0).sum()
                ),
                "loss_pnl_sum": float(
                    numeric_series(target[bool_series(target, "is_loss_trade")], "adjusted_pnl_num", default=0.0).sum()
                ),
                "extra_long_needed": int(repair_row.get("extra_long_needed", 0)) if repair_row is not None else 0,
                "extra_short_needed": int(repair_row.get("extra_short_needed", 0)) if repair_row is not None else 0,
            }
        )

    target_trades = pd.concat(target_trade_frames, ignore_index=True) if target_trade_frames else pd.DataFrame()
    target_trade_ids = set(target_trades["trade_id"].astype(str).tolist()) if not target_trades.empty else set()

    prior_all = build_prior_context_rows(
        trades,
        trades,
        context_specs=context_specs,
        large_loss_threshold=float(args.large_loss_threshold),
    )
    prior_target = prior_all[prior_all["trade_id"].astype(str).isin(target_trade_ids)].copy()
    hits = build_rule_hits(trades, prior_all)
    catalog = rule_catalog(context_specs)
    summary = summarize_rule_hits(hits, trades, target_trade_ids=target_trade_ids, catalog=catalog)
    target_out = add_target_hit_counts(target_trades, hits)
    month_summary = pd.DataFrame(month_summary_rows)

    run_dir = make_run_dir(resolve_path(args.output_root), args.run_label)
    target_out.to_csv(run_dir / "support_sufficient_loss_risk_target_trades.csv", index=False)
    month_summary.to_csv(run_dir / "support_sufficient_loss_risk_month_summary.csv", index=False)
    prior_target.to_csv(run_dir / "support_sufficient_loss_risk_prior_context.csv", index=False)
    prior_all.to_csv(run_dir / "support_sufficient_loss_risk_prior_context_all_trades.csv", index=False)
    hits.to_csv(run_dir / "support_sufficient_loss_risk_rule_hits.csv", index=False)
    summary.to_csv(run_dir / "support_sufficient_loss_risk_rule_summary.csv", index=False)
    trades.to_csv(run_dir / "support_sufficient_loss_risk_all_trade_features.csv", index=False)

    meta = {
        "config": config_path,
        "repair_targets": repair_targets_path,
        "current_trades": current_trades_path,
        "targets": parse_targets(args.targets),
        "context_specs": context_specs,
        "large_loss_threshold": args.large_loss_threshold,
        "note": (
            "Prior context rows use only selected trades with entry_decision_timestamp "
            "earlier than the evaluated trade. Rule hits are diagnostics, not an accepted "
            "blocking policy."
        ),
        "config_values": config,
    }
    (run_dir / "support_sufficient_loss_risk_meta.json").write_text(
        json.dumps(meta, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print(f"Wrote diagnostics to {run_dir}")
    if not month_summary.empty:
        print("\nTarget month summary:")
        print(month_summary.to_string(index=False))
    if not summary.empty:
        print("\nTop rule summary:")
        print(summary.head(int(args.print_rows)).to_string(index=False))
    return run_dir


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--context-specs", default=DEFAULT_CONTEXT_SPECS)
    parser.add_argument("--large-loss-threshold", type=float, default=-1.0)
    parser.add_argument("--output-root", default=str(ROOT / "data" / "reports" / "backtests"))
    parser.add_argument(
        "--run-label",
        default="20260703_entry_ev_00364_support_sufficient_loss_risk_prior",
    )
    parser.add_argument("--print-rows", type=int, default=12)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
