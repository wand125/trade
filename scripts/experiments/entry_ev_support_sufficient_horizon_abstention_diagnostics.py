#!/usr/bin/env python3
"""Diagnose abstention rules for predicted fixed-horizon choices."""

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
from entry_ev_support_sufficient_loss_risk_prior_diagnostics import (  # noqa: E402
    DEFAULT_CONTEXT_SPECS,
    DEFAULT_TARGETS,
    add_observable_trade_features,
    context_spec_name,
    parse_context_specs,
)
from entry_ev_upstream_universe_coverage_diagnostics import (  # noqa: E402
    DEFAULT_CONFIG,
    filter_repair_targets,
    resolve_path,
    role_to_family,
    select_repair_row,
)


def add_horizon_outcome_columns(
    trades: pd.DataFrame,
    *,
    min_delta: float,
) -> pd.DataFrame:
    output = trades.copy()
    output["pred_extension_delta"] = (
        numeric_series(output, "actual_at_pred_fixed_best_horizon")
        - numeric_series(output, "adjusted_pnl_num", default=0.0)
    )
    output["pred_extension_harm"] = output["pred_extension_delta"].lt(-abs(float(min_delta)))
    output["pred_extension_help"] = output["pred_extension_delta"].gt(abs(float(min_delta)))
    output["pred_extension_neutral"] = ~(output["pred_extension_harm"] | output["pred_extension_help"])
    return output


def horizon_prior_metric_row(frame: pd.DataFrame, *, min_delta: float) -> dict[str, Any]:
    count = int(len(frame))
    delta = numeric_series(frame, "pred_extension_delta", default=0.0)
    harm = delta.lt(-abs(float(min_delta)))
    help_ = delta.gt(abs(float(min_delta)))
    loss = numeric_series(frame, "adjusted_pnl_num", default=0.0).lt(0.0)
    return {
        "prior_count": count,
        "prior_month_count": int(frame["month"].astype(str).nunique()) if count else 0,
        "prior_extension_harm_count": int(harm.sum()),
        "prior_extension_help_count": int(help_.sum()),
        "prior_extension_neutral_count": int((~(harm | help_)).sum()) if count else 0,
        "prior_extension_delta_sum": float(delta.sum()) if count else 0.0,
        "prior_extension_delta_mean": float(delta.mean()) if count else np.nan,
        "prior_extension_harm_rate": float(harm.mean()) if count else np.nan,
        "prior_extension_help_rate": float(help_.mean()) if count else np.nan,
        "prior_extension_harm_delta_sum": float(delta[harm].sum()) if count else 0.0,
        "prior_extension_help_delta_sum": float(delta[help_].sum()) if count else 0.0,
        "prior_loss_count": int(loss.sum()),
        "prior_loss_rate": float(loss.mean()) if count else np.nan,
    }


def build_horizon_prior_context_rows(
    trades: pd.DataFrame,
    focus: pd.DataFrame,
    *,
    context_specs: list[list[str]],
    min_delta: float,
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
                    "pred_extension_delta": float(target.get("pred_extension_delta", np.nan)),
                    "pred_extension_harm": bool(target.get("pred_extension_harm", False)),
                    "pred_extension_help": bool(target.get("pred_extension_help", False)),
                    "context_spec": spec,
                    "context_key": key,
                    **horizon_prior_metric_row(prior, min_delta=min_delta),
                }
            )
    return pd.DataFrame(rows)


def feature_abstention_rule_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    loss_first = numeric_series(frame, "loss_first_prob")
    taken_ev = numeric_series(frame, "taken_ev")
    pred_best = numeric_series(frame, "pred_fixed_best_pred_pnl")
    side_gap = numeric_series(frame, "side_confidence_gap")
    horizon = numeric_series(frame, "pred_fixed_best_horizon_minutes", default=0.0)
    return {
        "loss_first_ge0p40": loss_first.ge(0.40),
        "pred_fixed_best_ge5": pred_best.ge(5.0),
        "pred_horizon_720": horizon.eq(720.0),
        "pred_horizon_720_lossfirst_ge0p40": horizon.eq(720.0) & loss_first.ge(0.40),
        "ev_ge5_lossfirst_lt0p30": taken_ev.ge(5.0) & loss_first.lt(0.30),
        "side_gap_ge0p15_lossfirst_lt0p30": side_gap.ge(0.15) & loss_first.lt(0.30),
        "lossfirst_ge0p40_or_pred_best_ge5": loss_first.ge(0.40) | pred_best.ge(5.0),
        "pred_best_ge5_or_h720_lossfirst_ge0p40": pred_best.ge(5.0)
        | (horizon.eq(720.0) & loss_first.ge(0.40)),
        "lossfirst_ge0p40_or_pred_best_ge5_or_ev_lowlf": loss_first.ge(0.40)
        | pred_best.ge(5.0)
        | (taken_ev.ge(5.0) & loss_first.lt(0.30)),
        "pred_best_ge5_or_sidegap_lowlf": pred_best.ge(5.0)
        | (side_gap.ge(0.15) & loss_first.lt(0.30)),
        "lossfirst_ge0p40_or_pred_best_ge5_or_sidegap_lowlf": loss_first.ge(0.40)
        | pred_best.ge(5.0)
        | (side_gap.ge(0.15) & loss_first.lt(0.30)),
    }


def prior_abstention_rule_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    count = numeric_series(frame, "prior_count", default=0.0)
    harm_rate = numeric_series(frame, "prior_extension_harm_rate")
    delta_mean = numeric_series(frame, "prior_extension_delta_mean")
    delta_sum = numeric_series(frame, "prior_extension_delta_sum", default=0.0)
    loss_rate = numeric_series(frame, "prior_loss_rate")
    return {
        "prior_count_ge3_harmrate_ge0p60": count.ge(3.0) & harm_rate.ge(0.60),
        "prior_count_ge5_harmrate_ge0p50": count.ge(5.0) & harm_rate.ge(0.50),
        "prior_count_ge3_delta_mean_lt0": count.ge(3.0) & delta_mean.lt(0.0),
        "prior_count_ge5_delta_sum_lt0": count.ge(5.0) & delta_sum.lt(0.0),
        "prior_count_ge3_lossrate_ge0p60": count.ge(3.0) & loss_rate.ge(0.60),
    }


def abstention_rule_catalog(context_specs: list[list[str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for rule in feature_abstention_rule_masks(pd.DataFrame(index=[0])):
        rows.append({"rule": rule, "rule_family": "feature", "context_spec": "feature"})
    for columns in context_specs:
        spec = context_spec_name(columns)
        for rule in prior_abstention_rule_masks(pd.DataFrame(index=[0])):
            rows.append({"rule": rule, "rule_family": "prior_context", "context_spec": spec})
    return pd.DataFrame(rows)


def build_abstention_rule_hits(trades: pd.DataFrame, prior_context: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for rule, mask in feature_abstention_rule_masks(trades).items():
        hit = trades.loc[mask.fillna(False)].copy()
        if hit.empty:
            continue
        hit["rule"] = rule
        hit["rule_family"] = "feature"
        hit["context_spec"] = "feature"
        hit["context_key"] = ""
        rows.append(hit)
    if not prior_context.empty:
        for rule, mask in prior_abstention_rule_masks(prior_context).items():
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
            ]
        )
    return pd.concat(rows, ignore_index=True, sort=False)


def summarize_abstention_frame(
    frame: pd.DataFrame,
    *,
    total_harm_count: int,
    total_extension_delta: float,
) -> dict[str, Any]:
    if frame.empty:
        return {
            "flagged_trade_count": 0,
            "flagged_harm_count": 0,
            "flagged_help_count": 0,
            "flagged_neutral_count": 0,
            "flagged_extension_delta_sum": 0.0,
            "flagged_harm_delta_sum": 0.0,
            "flagged_help_delta_sum": 0.0,
            "flagged_harm_rate": np.nan,
            "harm_recall": 0.0,
            "abstain_delta_vs_follow_if_flagged": 0.0,
            "extension_delta_after_abstention": float(total_extension_delta),
        }
    delta = numeric_series(frame, "pred_extension_delta", default=0.0)
    harm = bool_series(frame, "pred_extension_harm", default=False)
    help_ = bool_series(frame, "pred_extension_help", default=False)
    neutral = ~(harm | help_)
    count = int(len(frame))
    extension_after = float(total_extension_delta - delta.sum())
    return {
        "flagged_trade_count": count,
        "flagged_harm_count": int(harm.sum()),
        "flagged_help_count": int(help_.sum()),
        "flagged_neutral_count": int(neutral.sum()),
        "flagged_extension_delta_sum": float(delta.sum()),
        "flagged_harm_delta_sum": float(delta[harm].sum()) if harm.any() else 0.0,
        "flagged_help_delta_sum": float(delta[help_].sum()) if help_.any() else 0.0,
        "flagged_harm_rate": float(harm.sum() / count) if count else np.nan,
        "harm_recall": float(harm.sum() / total_harm_count) if total_harm_count else 0.0,
        "abstain_delta_vs_follow_if_flagged": float(-delta.sum()),
        "extension_delta_after_abstention": extension_after,
    }


def summarize_abstention_rule_hits(
    hits: pd.DataFrame,
    trades: pd.DataFrame,
    *,
    target_trade_ids: set[str],
    catalog: pd.DataFrame,
) -> pd.DataFrame:
    trade_index = trades.drop_duplicates("trade_id").set_index("trade_id", drop=False)
    total_harm_count = int(bool_series(trades, "pred_extension_harm").sum())
    total_extension_delta = float(numeric_series(trades, "pred_extension_delta", default=0.0).sum())
    target = trades[trades["trade_id"].astype(str).isin(target_trade_ids)].copy()
    target_harm_count = int(bool_series(target, "pred_extension_harm").sum())
    target_extension_delta = float(numeric_series(target, "pred_extension_delta", default=0.0).sum())

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
                "evaluated_harm_count": total_harm_count,
                "evaluated_extension_delta_sum": total_extension_delta,
                **summarize_abstention_frame(
                    flagged,
                    total_harm_count=total_harm_count,
                    total_extension_delta=total_extension_delta,
                ),
                "target_trade_count": int(len(target)),
                "target_harm_count": target_harm_count,
                "target_extension_delta_sum": target_extension_delta,
                **{
                    f"target_{key}": value
                    for key, value in summarize_abstention_frame(
                        target_flagged,
                        total_harm_count=target_harm_count,
                        total_extension_delta=target_extension_delta,
                    ).items()
                },
            }
        )
    return pd.DataFrame(rows).sort_values(
        [
            "target_abstain_delta_vs_follow_if_flagged",
            "abstain_delta_vs_follow_if_flagged",
            "target_harm_recall",
            "harm_recall",
        ],
        ascending=[False, False, False, False],
    )


def add_target_hit_counts(target: pd.DataFrame, hits: pd.DataFrame) -> pd.DataFrame:
    output = target.copy()
    if hits.empty:
        output["abstention_rule_hit_count"] = 0
        output["feature_rule_hit_count"] = 0
        output["prior_rule_hit_count"] = 0
        output["abstention_rules"] = ""
        return output
    grouped = (
        hits.groupby("trade_id")
        .agg(
            abstention_rule_hit_count=("rule", "count"),
            feature_rule_hit_count=("rule_family", lambda values: int((values == "feature").sum())),
            prior_rule_hit_count=("rule_family", lambda values: int((values == "prior_context").sum())),
            abstention_rules=("rule", lambda values: ";".join(sorted(set(map(str, values))))),
        )
        .reset_index()
    )
    output = output.merge(grouped, on="trade_id", how="left")
    for column in ["abstention_rule_hit_count", "feature_rule_hit_count", "prior_rule_hit_count"]:
        output[column] = numeric_series(output, column, default=0.0).astype(int)
    output["abstention_rules"] = output["abstention_rules"].fillna("")
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
    trades = add_horizon_outcome_columns(trades, min_delta=float(args.min_delta))

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
        target_delta = float(numeric_series(target, "pred_extension_delta", default=0.0).sum())
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
                "current_month_pnl": month_pnl,
                "predicted_follow_extension_delta_sum": target_delta,
                "month_pnl_if_follow_pred_horizon_all": float(month_pnl + target_delta),
                "month_pnl_if_abstain_all_pred_horizon": month_pnl,
                "trade_count": int(len(target)),
                "pred_extension_harm_count": int(bool_series(target, "pred_extension_harm").sum()),
                "pred_extension_help_count": int(bool_series(target, "pred_extension_help").sum()),
                "extra_long_needed": int(repair_row.get("extra_long_needed", 0)) if repair_row is not None else 0,
                "extra_short_needed": int(repair_row.get("extra_short_needed", 0)) if repair_row is not None else 0,
            }
        )

    target_trades = pd.concat(target_trade_frames, ignore_index=True) if target_trade_frames else pd.DataFrame()
    target_trade_ids = set(target_trades["trade_id"].astype(str).tolist()) if not target_trades.empty else set()

    prior_all = build_horizon_prior_context_rows(
        trades,
        trades,
        context_specs=context_specs,
        min_delta=float(args.min_delta),
    )
    prior_target = prior_all[prior_all["trade_id"].astype(str).isin(target_trade_ids)].copy()
    hits = build_abstention_rule_hits(trades, prior_all)
    catalog = abstention_rule_catalog(context_specs)
    summary = summarize_abstention_rule_hits(hits, trades, target_trade_ids=target_trade_ids, catalog=catalog)
    target_out = add_target_hit_counts(target_trades, hits)
    month_summary = pd.DataFrame(month_summary_rows)

    run_dir = make_run_dir(resolve_path(args.output_root), args.run_label)
    target_out.to_csv(run_dir / "support_sufficient_horizon_abstention_target_trades.csv", index=False)
    month_summary.to_csv(run_dir / "support_sufficient_horizon_abstention_month_summary.csv", index=False)
    prior_target.to_csv(run_dir / "support_sufficient_horizon_abstention_prior_context.csv", index=False)
    prior_all.to_csv(run_dir / "support_sufficient_horizon_abstention_prior_context_all_trades.csv", index=False)
    hits.to_csv(run_dir / "support_sufficient_horizon_abstention_rule_hits.csv", index=False)
    summary.to_csv(run_dir / "support_sufficient_horizon_abstention_rule_summary.csv", index=False)
    trades.to_csv(run_dir / "support_sufficient_horizon_abstention_all_trade_features.csv", index=False)

    meta = {
        "config": config_path,
        "repair_targets": repair_targets_path,
        "current_trades": current_trades_path,
        "targets": parse_targets(args.targets),
        "context_specs": context_specs,
        "large_loss_threshold": args.large_loss_threshold,
        "min_delta": args.min_delta,
        "note": (
            "Outcome columns compare current exits against the predicted fixed-horizon argmax. "
            "Rules are diagnostic abstention screens; actual fixed-horizon PnL is not used "
            "as a feature."
        ),
        "config_values": config,
    }
    (run_dir / "support_sufficient_horizon_abstention_meta.json").write_text(
        json.dumps(meta, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print(f"Wrote diagnostics to {run_dir}")
    if not month_summary.empty:
        print("\nTarget month summary:")
        print(month_summary.to_string(index=False))
    if not summary.empty:
        print("\nTop abstention rule summary:")
        print(summary.head(int(args.print_rows)).to_string(index=False))
    return run_dir


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--context-specs", default=DEFAULT_CONTEXT_SPECS)
    parser.add_argument("--large-loss-threshold", type=float, default=-1.0)
    parser.add_argument("--min-delta", type=float, default=0.0)
    parser.add_argument("--output-root", default=str(ROOT / "data" / "reports" / "backtests"))
    parser.add_argument(
        "--run-label",
        default="20260703_entry_ev_00365_support_sufficient_horizon_abstention",
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
