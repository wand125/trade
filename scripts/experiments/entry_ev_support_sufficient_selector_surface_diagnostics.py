#!/usr/bin/env python3
"""Diagnose loss-risk plus calibrated replacement selector surfaces."""

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
from entry_ev_support_sufficient_loss_risk_prior_diagnostics import (  # noqa: E402
    DEFAULT_CONTEXT_SPECS as DEFAULT_RISK_CONTEXT_SPECS,
    add_observable_trade_features,
    build_prior_context_rows,
    feature_rule_masks,
    parse_context_specs as parse_risk_context_specs,
    prior_rule_masks,
)
from entry_ev_support_sufficient_negative_month_repair_diagnostics import (  # noqa: E402
    add_current_trade_repair_columns,
    candidate_pool_for_loss,
    load_extended_side_rows,
)
from entry_ev_support_sufficient_replacement_calibration_diagnostics import (  # noqa: E402
    DEFAULT_CONFIG,
    DEFAULT_CONTEXT_SPECS,
    DEFAULT_TARGETS,
    SCORE_COLUMNS,
    add_prior_calibration,
    choose_top_candidate,
    load_family_side_rows,
    parse_context_specs,
)
from entry_ev_thin_month_opposite_candidate_diagnostics import (  # noqa: E402
    bool_series,
    local_json_default,
    numeric_series,
    read_current_trades,
)
from entry_ev_upstream_universe_coverage_diagnostics import (  # noqa: E402
    filter_repair_targets,
    resolve_path,
    role_to_family,
    select_repair_row,
)


DEFAULT_RISK_SELECTORS = (
    "feature:ev_ge5_lossfirst_lt0p30;"
    "feature:side_gap_ge0p15_lossfirst_lt0p30;"
    "feature:lossfirst_ge0p40_or_ev_ge5_lossfirst_lt0p30;"
    "prior:direction,combined_regime:prior_count_ge5_lossrate_ge0p50;"
    "combined:any_lossrisk;"
    "score:loss_first_prob;"
    "score:ev_low_lossfirst;"
    "oracle:worst_loss"
)
DEFAULT_SCORE_MODES = "prior_actual_mean,bias_corrected,raw_pred_fixed,side_score"
AUTO_TARGET_VALUES = {"auto", "auto_support_sufficient_negative"}
TARGET_OUTCOME_REPLACEMENT_GAPS = {
    "loss_selected_no_replacement",
    "loss_replacement_degrades",
    "loss_replacement_improves_but_still_negative",
}


def parse_int_grid(value: str) -> list[int]:
    items: list[int] = []
    for part in str(value).split(","):
        text = part.strip()
        if text:
            items.append(int(text))
    if not items:
        raise argparse.ArgumentTypeError("at least one integer is required")
    return items


def parse_float_grid(value: str) -> list[float]:
    items: list[float] = []
    for part in str(value).split(","):
        text = part.strip().lower()
        if not text:
            continue
        if text in {"none", "-inf", "all"}:
            items.append(float("-inf"))
        else:
            items.append(float(text))
    if not items:
        raise argparse.ArgumentTypeError("at least one float is required")
    return items


def parse_semicolon(value: str) -> list[str]:
    items = [part.strip() for part in str(value).split(";") if part.strip()]
    if not items:
        raise argparse.ArgumentTypeError("at least one item is required")
    return items


def parse_score_modes(value: str) -> list[str]:
    modes = [part.strip() for part in str(value).split(",") if part.strip()]
    unknown = sorted(set(modes) - set(SCORE_COLUMNS))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown score modes: {unknown}")
    if not modes:
        raise argparse.ArgumentTypeError("at least one score mode is required")
    return modes


def timestamp_key(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, utc=True, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def infer_target_side(trades: pd.DataFrame) -> str:
    if trades.empty or "direction" not in trades.columns:
        return "both"
    frame = trades.copy()
    pnl = numeric_series(frame, "adjusted_pnl", default=0.0)
    losses = frame.loc[pnl.lt(0.0)].copy()
    if losses.empty:
        counts = frame["direction"].astype(str).value_counts()
        return str(counts.index[0]) if len(counts) else "both"
    losses["_loss_abs"] = -numeric_series(losses, "adjusted_pnl", default=0.0)
    by_side = losses.groupby(losses["direction"].astype(str))["_loss_abs"].sum()
    return str(by_side.sort_values(ascending=False).index[0]) if len(by_side) else "both"


def build_target_inventory(
    *,
    current: pd.DataFrame,
    repair_targets: pd.DataFrame,
) -> pd.DataFrame:
    if current.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    current_frame = current.copy()
    current_frame["month"] = current_frame["month"].astype(str).str.slice(0, 7)
    for (role, family, month), group in current_frame.groupby(
        ["role", "family", "month"],
        dropna=False,
    ):
        repair_row = select_repair_row(repair_targets, role=str(role), month=str(month))
        pnl = numeric_series(group, "adjusted_pnl", default=0.0)
        extra_long = int(repair_row.get("extra_long_needed", 0)) if repair_row is not None else 0
        extra_short = int(repair_row.get("extra_short_needed", 0)) if repair_row is not None else 0
        rows.append(
            {
                "role": str(role),
                "family": str(family),
                "month": str(month),
                "target_side": infer_target_side(group),
                "month_pnl": float(pnl.sum()),
                "trade_count": int(len(group)),
                "loss_trade_count": int(pnl.lt(0.0).sum()),
                "long_trade_count": int(group["direction"].astype(str).eq("long").sum())
                if "direction" in group.columns
                else 0,
                "short_trade_count": int(group["direction"].astype(str).eq("short").sum())
                if "direction" in group.columns
                else 0,
                "repair_target_present": bool(repair_row is not None),
                "extra_long_needed": extra_long,
                "extra_short_needed": extra_short,
                "extra_trades_needed": extra_long + extra_short,
                "support_sufficient_negative_month": bool(
                    pnl.sum() < 0.0
                    and repair_row is not None
                    and extra_long == 0
                    and extra_short == 0
                ),
                "support_limited_negative_month": bool(
                    pnl.sum() < 0.0
                    and repair_row is not None
                    and (extra_long > 0 or extra_short > 0)
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["month_pnl", "role", "month"]).reset_index(drop=True)


def resolve_target_specs(
    targets: str,
    *,
    current: pd.DataFrame,
    repair_targets: pd.DataFrame,
) -> tuple[list[tuple[str, str, str]], pd.DataFrame]:
    inventory = build_target_inventory(current=current, repair_targets=repair_targets)
    if str(targets).strip() not in AUTO_TARGET_VALUES:
        return parse_targets(targets), inventory
    selected = inventory[bool_series(inventory, "support_sufficient_negative_month")].copy()
    specs = [
        (str(row["role"]), str(row["month"]), str(row["target_side"]))
        for _, row in selected.iterrows()
    ]
    return specs, inventory


def resolve_inventory_target_specs(
    path: Path,
    *,
    min_support_sufficient_configs: int,
    min_metric_parents: int,
    max_targets: int,
    target_side: str,
) -> tuple[list[tuple[str, str, str]], pd.DataFrame]:
    inventory = pd.read_csv(path)
    required = {
        "role",
        "family",
        "month",
        "support_sufficient_config_count",
        "support_limited_config_count",
        "metric_parent_count",
        "best_month_pnl",
    }
    missing = sorted(required - set(inventory.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    selected = inventory.copy()
    selected["month"] = selected["month"].astype(str).str.slice(0, 7)
    selected["support_sufficient_config_count"] = numeric_series(
        selected,
        "support_sufficient_config_count",
        default=0.0,
    ).astype(int)
    selected["support_limited_config_count"] = numeric_series(
        selected,
        "support_limited_config_count",
        default=0.0,
    ).astype(int)
    selected["metric_parent_count"] = numeric_series(
        selected,
        "metric_parent_count",
        default=0.0,
    ).astype(int)
    selected["best_month_pnl"] = numeric_series(selected, "best_month_pnl", default=np.nan)
    selected["worst_month_pnl"] = numeric_series(selected, "worst_month_pnl", default=np.nan)
    selected = selected[
        selected["support_sufficient_config_count"].ge(int(min_support_sufficient_configs))
        & selected["metric_parent_count"].ge(int(min_metric_parents))
    ].copy()
    selected = selected.sort_values(
        [
            "support_sufficient_config_count",
            "metric_parent_count",
            "best_month_pnl",
        ],
        ascending=[False, False, False],
    )
    if max_targets > 0:
        selected = selected.head(int(max_targets)).copy()
    selected["target_side"] = str(target_side)
    selected["target_source"] = "external_support_negative_inventory"
    selected["support_sufficient_negative_month"] = True
    selected["support_limited_negative_month"] = False
    specs = [
        (str(row["role"]), str(row["month"]), str(row["target_side"]))
        for _, row in selected.iterrows()
    ]
    return specs, selected.reset_index(drop=True)


def feature_score(frame: pd.DataFrame, selector: str) -> pd.Series:
    loss_first = numeric_series(frame, "loss_first_prob", default=0.0)
    taken_ev = numeric_series(frame, "taken_ev", default=0.0)
    side_gap = numeric_series(frame, "side_confidence_gap", default=0.0)
    pred_best = numeric_series(frame, "pred_fixed_best_pred_pnl", default=0.0)
    if selector == "loss_first_ge0p40":
        return loss_first
    if selector == "ev_ge5_lossfirst_lt0p30":
        return taken_ev + pred_best.clip(lower=0.0) * 0.01
    if selector == "side_gap_ge0p15_lossfirst_lt0p30":
        return side_gap + taken_ev.clip(lower=0.0) * 0.01
    if selector == "lossfirst_ge0p40_or_ev_ge5_lossfirst_lt0p30":
        return loss_first + taken_ev.clip(lower=0.0) * 0.02 + side_gap
    return loss_first + taken_ev.clip(lower=0.0) * 0.01 + side_gap


def risk_prior_features(prior_context: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "trade_id",
        "risk_prior_context_count",
        "risk_prior_max_count",
        "risk_prior_max_month_count",
        "risk_prior_max_loss_rate",
        "risk_prior_max_large_loss_rate",
        "risk_prior_min_pnl_mean",
        "risk_prior_min_pnl_sum",
    ]
    if prior_context.empty:
        return pd.DataFrame(columns=columns)
    frame = prior_context.copy()
    frame["prior_count_num"] = numeric_series(frame, "prior_count", default=0.0)
    frame["prior_month_count_num"] = numeric_series(frame, "prior_month_count", default=0.0)
    frame["prior_loss_rate_num"] = numeric_series(frame, "prior_loss_rate", default=np.nan)
    frame["prior_large_loss_rate_num"] = numeric_series(
        frame,
        "prior_large_loss_rate",
        default=np.nan,
    )
    frame["prior_pnl_mean_num"] = numeric_series(frame, "prior_pnl_mean", default=np.nan)
    frame["prior_pnl_sum_num"] = numeric_series(frame, "prior_pnl_sum", default=np.nan)
    grouped = frame.groupby("trade_id", dropna=False).agg(
        risk_prior_context_count=("context_spec", "count"),
        risk_prior_max_count=("prior_count_num", "max"),
        risk_prior_max_month_count=("prior_month_count_num", "max"),
        risk_prior_max_loss_rate=("prior_loss_rate_num", "max"),
        risk_prior_max_large_loss_rate=("prior_large_loss_rate_num", "max"),
        risk_prior_min_pnl_mean=("prior_pnl_mean_num", "min"),
        risk_prior_min_pnl_sum=("prior_pnl_sum_num", "min"),
    )
    return grouped.reset_index()[columns]


def risk_rule_hit_table(trades: pd.DataFrame, prior_context: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for rule, mask in feature_rule_masks(trades).items():
        hit = trades.loc[mask.fillna(False), ["trade_id"]].copy()
        if hit.empty:
            continue
        hit["risk_selector"] = f"feature:{rule}"
        hit["risk_rule_family"] = "feature"
        hit["risk_rule"] = rule
        hit["risk_context_spec"] = "feature"
        rows.append(hit)
    if not prior_context.empty:
        for rule, mask in prior_rule_masks(prior_context).items():
            hit = prior_context.loc[
                mask.fillna(False),
                ["trade_id", "context_spec", "context_key"],
            ].copy()
            if hit.empty:
                continue
            hit["risk_selector"] = "prior:" + hit["context_spec"].astype(str) + ":" + rule
            hit["risk_rule_family"] = "prior_context"
            hit["risk_rule"] = rule
            hit["risk_context_spec"] = hit["context_spec"].astype(str)
            rows.append(hit.drop(columns=["context_spec"], errors="ignore"))
    if not rows:
        return pd.DataFrame(
            columns=[
                "trade_id",
                "risk_selector",
                "risk_rule_family",
                "risk_rule",
                "risk_context_spec",
                "context_key",
            ]
        )
    return pd.concat(rows, ignore_index=True, sort=False)


def add_risk_columns(trades: pd.DataFrame, prior_context: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = trades.copy()
    output = output.merge(risk_prior_features(prior_context), on="trade_id", how="left")
    for column in [
        "risk_prior_context_count",
        "risk_prior_max_count",
        "risk_prior_max_month_count",
    ]:
        output[column] = numeric_series(output, column, default=0.0)
    hits = risk_rule_hit_table(output, prior_context)
    if hits.empty:
        output["risk_rule_hit_count"] = 0
        output["risk_feature_rule_hit_count"] = 0
        output["risk_prior_rule_hit_count"] = 0
        output["risk_rule_names"] = ""
        output["risk_selectors_hit"] = ""
    else:
        grouped = hits.groupby("trade_id").agg(
            risk_rule_hit_count=("risk_rule", "count"),
            risk_feature_rule_hit_count=(
                "risk_rule_family",
                lambda values: int((values == "feature").sum()),
            ),
            risk_prior_rule_hit_count=(
                "risk_rule_family",
                lambda values: int((values == "prior_context").sum()),
            ),
            risk_rule_names=("risk_rule", lambda values: ";".join(sorted(set(map(str, values))))),
            risk_selectors_hit=(
                "risk_selector",
                lambda values: ";".join(sorted(set(map(str, values)))),
            ),
        )
        output = output.merge(grouped.reset_index(), on="trade_id", how="left")
        for column in [
            "risk_rule_hit_count",
            "risk_feature_rule_hit_count",
            "risk_prior_rule_hit_count",
        ]:
            output[column] = numeric_series(output, column, default=0.0).astype(int)
        output["risk_rule_names"] = output["risk_rule_names"].fillna("")
        output["risk_selectors_hit"] = output["risk_selectors_hit"].fillna("")

    loss_first = numeric_series(output, "loss_first_prob", default=0.0)
    taken_ev = numeric_series(output, "taken_ev", default=0.0)
    side_gap = numeric_series(output, "side_confidence_gap", default=0.0)
    prior_loss_rate = numeric_series(output, "risk_prior_max_loss_rate", default=0.0).fillna(0.0)
    output["combined_loss_risk_score"] = (
        numeric_series(output, "risk_rule_hit_count", default=0.0)
        + loss_first
        + taken_ev.clip(lower=0.0) * 0.03
        + side_gap
        + prior_loss_rate
    )
    return output, hits


def selector_mask_and_score(
    trades: pd.DataFrame,
    *,
    selector: str,
) -> tuple[pd.Series, pd.Series, str]:
    if selector.startswith("feature:"):
        rule = selector.split(":", 1)[1]
        masks = feature_rule_masks(trades)
        if rule not in masks:
            raise ValueError(f"unknown feature risk selector: {selector}")
        return masks[rule].fillna(False), feature_score(trades, rule), "feature"
    if selector.startswith("prior:"):
        hits = trades["risk_selectors_hit"].fillna("").astype(str)
        mask = hits.map(lambda text: selector in set(part for part in text.split(";") if part))
        return mask, numeric_series(trades, "combined_loss_risk_score", default=0.0), "prior_context"
    if selector == "combined:any_lossrisk":
        mask = numeric_series(trades, "risk_rule_hit_count", default=0.0).gt(0.0)
        return mask, numeric_series(trades, "combined_loss_risk_score", default=0.0), "combined"
    if selector == "score:loss_first_prob":
        score = numeric_series(trades, "loss_first_prob", default=-np.inf)
        return score.notna(), score, "score"
    if selector == "score:ev_low_lossfirst":
        loss_first = numeric_series(trades, "loss_first_prob", default=np.inf)
        taken_ev = numeric_series(trades, "taken_ev", default=-np.inf)
        mask = loss_first.lt(0.30) & taken_ev.notna()
        return mask, taken_ev, "score"
    if selector == "oracle:worst_loss":
        adjusted = numeric_series(trades, "adjusted_pnl", default=0.0)
        mask = adjusted.lt(0.0)
        return mask, -adjusted, "oracle"
    raise ValueError(f"unknown risk selector: {selector}")


def risk_selector_family(selector: str) -> str:
    if selector.startswith("feature:"):
        return "feature"
    if selector.startswith("prior:"):
        return "prior_context"
    if selector.startswith("score:"):
        return "score"
    if selector.startswith("oracle:"):
        return "oracle"
    if selector.startswith("combined:"):
        return "combined"
    return "unknown"


def choose_trade_by_risk(trades: pd.DataFrame, *, selector: str) -> pd.Series | None:
    mask, score, _family = selector_mask_and_score(trades, selector=selector)
    candidates = trades.loc[mask.fillna(False)].copy()
    if candidates.empty:
        return None
    candidates["_risk_selection_score"] = score.loc[candidates.index]
    candidates["_entry_time"] = pd.to_datetime(
        candidates["entry_decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    return candidates.sort_values(
        ["_risk_selection_score", "risk_rule_hit_count", "_entry_time"],
        ascending=[False, False, True],
    ).iloc[0]


def candidate_support_mask(
    pool: pd.DataFrame,
    *,
    min_prior_count: int,
    min_prior_month_count: int,
    min_prior_actual_mean: float,
) -> pd.Series:
    if pool.empty:
        return pd.Series(False, index=pool.index)
    mask = numeric_series(pool, "prior_count", default=0.0).ge(float(min_prior_count))
    mask &= numeric_series(pool, "prior_month_count", default=0.0).ge(float(min_prior_month_count))
    if np.isfinite(min_prior_actual_mean):
        mask &= numeric_series(pool, "prior_actual_mean", default=-np.inf).ge(
            float(min_prior_actual_mean)
        )
    return mask.fillna(False)


def choose_supported_candidate(
    pool: pd.DataFrame,
    *,
    score_mode: str,
    min_prior_count: int,
    min_prior_month_count: int,
    min_prior_actual_mean: float,
) -> pd.Series | None:
    filtered = pool.loc[
        candidate_support_mask(
            pool,
            min_prior_count=min_prior_count,
            min_prior_month_count=min_prior_month_count,
            min_prior_actual_mean=min_prior_actual_mean,
        )
    ].copy()
    return choose_top_candidate(filtered, score_mode=score_mode)


def supported_candidate_count(
    pool: pd.DataFrame,
    *,
    min_prior_count: int,
    min_prior_month_count: int,
    min_prior_actual_mean: float,
) -> int:
    return int(
        candidate_support_mask(
            pool,
            min_prior_count=min_prior_count,
            min_prior_month_count=min_prior_month_count,
            min_prior_actual_mean=min_prior_actual_mean,
        ).sum()
    )


def selector_choice_row(
    *,
    role: str,
    family: str,
    month: str,
    month_pnl: float,
    risk_selector: str,
    risk_trade: pd.Series | None,
    replacement_score_mode: str,
    calibration_min_context_count: int,
    candidate_min_prior_count: int,
    candidate_min_prior_month_count: int,
    candidate_min_prior_actual_mean: float,
    candidate: pd.Series | None,
    candidate_rows: int,
    supported_candidate_rows: int,
) -> dict[str, Any]:
    base = {
        "role": role,
        "family": family,
        "month": month,
        "baseline_month_pnl": float(month_pnl),
        "risk_selector": risk_selector,
        "risk_selector_family": risk_selector_family(risk_selector),
        "replacement_score_mode": replacement_score_mode,
        "calibration_min_context_count": int(calibration_min_context_count),
        "candidate_min_prior_count": int(candidate_min_prior_count),
        "candidate_min_prior_month_count": int(candidate_min_prior_month_count),
        "candidate_min_prior_actual_mean": float(candidate_min_prior_actual_mean),
        "candidate_rows": int(candidate_rows),
        "supported_candidate_rows": int(supported_candidate_rows),
    }
    if risk_trade is None:
        return {
            **base,
            "risk_trade_selected": False,
            "risk_trade_id": "",
            "risk_trade_direction": "",
            "risk_trade_timestamp": "",
            "risk_trade_adjusted_pnl": np.nan,
            "risk_trade_is_loss": False,
            "risk_trade_rule_hit_count": 0,
            "skip_only_month_pnl": float(month_pnl),
            "replacement_chosen": False,
            "month_pnl_after_replacement": float(month_pnl),
            "delta_vs_baseline": 0.0,
        }

    adjusted = float(risk_trade.get("adjusted_pnl", np.nan))
    skip_only = float(month_pnl - adjusted)
    risk_base = {
        **base,
        "risk_trade_selected": True,
        "risk_trade_id": str(risk_trade["trade_id"]),
        "risk_trade_direction": str(risk_trade.get("direction", "")),
        "risk_trade_timestamp": str(risk_trade.get("entry_decision_timestamp", "")),
        "risk_trade_adjusted_pnl": adjusted,
        "risk_trade_is_loss": bool(adjusted < 0.0),
        "risk_trade_rule_hit_count": int(risk_trade.get("risk_rule_hit_count", 0)),
        "risk_trade_feature_rule_hit_count": int(risk_trade.get("risk_feature_rule_hit_count", 0)),
        "risk_trade_prior_rule_hit_count": int(risk_trade.get("risk_prior_rule_hit_count", 0)),
        "risk_trade_loss_first_prob": float(risk_trade.get("loss_first_prob", np.nan)),
        "risk_trade_taken_ev": float(risk_trade.get("taken_ev", np.nan)),
        "risk_trade_side_confidence_gap": float(risk_trade.get("side_confidence_gap", np.nan)),
        "risk_trade_prior_max_loss_rate": float(risk_trade.get("risk_prior_max_loss_rate", np.nan)),
        "risk_trade_rules": str(risk_trade.get("risk_rule_names", "")),
        "skip_only_month_pnl": skip_only,
    }
    if candidate is None:
        return {
            **risk_base,
            "replacement_chosen": False,
            "candidate_side": "",
            "candidate_timestamp": "",
            "candidate_stage": "",
            "selection_score": np.nan,
            "candidate_pred_horizon": 0,
            "candidate_pred_pnl": np.nan,
            "candidate_actual_at_pred_horizon": np.nan,
            "candidate_oracle_fixed_best_actual": np.nan,
            "calibration_context_spec": "",
            "calibration_context_key": "",
            "prior_count": 0,
            "prior_month_count": 0,
            "prior_actual_mean": np.nan,
            "month_pnl_after_replacement": float(month_pnl),
            "delta_vs_baseline": 0.0,
        }

    score_column = SCORE_COLUMNS[replacement_score_mode]
    actual_at_pred = float(candidate["candidate_actual_at_pred_fixed_best_horizon"])
    month_after = skip_only + actual_at_pred
    return {
        **risk_base,
        "replacement_chosen": True,
        "candidate_side": str(candidate["side"]),
        "candidate_timestamp": str(candidate["decision_timestamp"]),
        "candidate_stage": str(candidate["candidate_stage"]),
        "selection_score": float(candidate.get(score_column, np.nan)),
        "side_score": float(candidate.get("side_score", np.nan)),
        "candidate_pred_horizon": int(candidate["candidate_pred_fixed_best_horizon_minutes"]),
        "candidate_pred_pnl": float(candidate["candidate_pred_fixed_best_pred_pnl"]),
        "candidate_actual_at_pred_horizon": actual_at_pred,
        "candidate_oracle_fixed_best_actual": float(candidate["candidate_fixed_best_actual_pnl_oracle"]),
        "calibration_context_spec": str(candidate.get("calibration_context_spec", "")),
        "calibration_context_key": str(candidate.get("calibration_context_key", "")),
        "prior_count": int(candidate.get("prior_count", 0)),
        "prior_month_count": int(candidate.get("prior_month_count", 0)),
        "prior_bias_mean": float(candidate.get("prior_bias_mean", np.nan)),
        "prior_mae": float(candidate.get("prior_mae", np.nan)),
        "prior_actual_mean": float(candidate.get("prior_actual_mean", np.nan)),
        "month_pnl_after_replacement": float(month_after),
        "delta_vs_baseline": float(month_after - month_pnl),
    }


def safe_rate(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else np.nan


def add_target_outcome_columns(choices: pd.DataFrame) -> pd.DataFrame:
    output = choices.copy()
    risk_selected = bool_series(output, "risk_trade_selected", default=False)
    risk_loss = bool_series(output, "risk_trade_is_loss", default=False)
    replacement = bool_series(output, "replacement_chosen", default=False)
    supported = numeric_series(output, "supported_candidate_rows", default=0.0).gt(0.0)
    delta = numeric_series(output, "delta_vs_baseline", default=0.0)
    after = numeric_series(output, "month_pnl_after_replacement", default=np.nan)
    category = pd.Series("unknown", index=output.index, dtype=object)
    category.loc[~risk_selected] = "no_risk_trade"
    category.loc[risk_selected & ~risk_loss] = "risk_trade_winner"
    category.loc[risk_selected & risk_loss & ~supported] = "loss_selected_no_supported_candidate"
    category.loc[risk_selected & risk_loss & supported & ~replacement] = "loss_selected_no_replacement"
    category.loc[risk_selected & risk_loss & replacement & delta.lt(0.0)] = "loss_replacement_degrades"
    category.loc[
        risk_selected
        & risk_loss
        & replacement
        & delta.ge(0.0)
        & after.lt(0.0)
    ] = "loss_replacement_improves_but_still_negative"
    category.loc[
        risk_selected
        & risk_loss
        & replacement
        & delta.ge(0.0)
        & after.ge(0.0)
    ] = "loss_replacement_repairs_month"
    output["target_outcome_category"] = category
    output["target_outcome_success"] = category.eq("loss_replacement_repairs_month")
    output["target_outcome_candidate_gap"] = category.eq("loss_selected_no_supported_candidate")
    output["target_outcome_risk_gap"] = category.isin(["no_risk_trade", "risk_trade_winner"])
    output["target_outcome_replacement_gap"] = category.isin(TARGET_OUTCOME_REPLACEMENT_GAPS)
    return output


def optional_max_count_pass(count: int, threshold: int) -> bool:
    return True if int(threshold) < 0 else bool(count <= int(threshold))


def summarize_surface(
    choices: pd.DataFrame,
    *,
    min_loss_selection_precision: float = 0.5,
    max_winner_trade_selected: int = 0,
    max_baseline_positive_degraded: int = 0,
    min_current_negative_delta: float = 0.0,
    min_target_outcome_success_count: int = 1,
    max_target_candidate_gap_count: int = 0,
    max_target_risk_gap_count: int = -1,
    max_target_replacement_gap_count: int = 0,
) -> pd.DataFrame:
    if choices.empty:
        return pd.DataFrame()
    choices = add_target_outcome_columns(choices)
    group_cols = [
        "risk_selector",
        "replacement_score_mode",
        "calibration_min_context_count",
        "candidate_min_prior_count",
        "candidate_min_prior_month_count",
        "candidate_min_prior_actual_mean",
    ]
    rows: list[dict[str, Any]] = []
    for keys, group in choices.groupby(group_cols, dropna=False):
        replacement = bool_series(group, "replacement_chosen", default=False)
        risk_selected = bool_series(group, "risk_trade_selected", default=False)
        risk_loss = bool_series(group, "risk_trade_is_loss", default=False)
        risk_winner = risk_selected & ~risk_loss
        categories = group["target_outcome_category"].astype(str)
        pnl = numeric_series(group, "month_pnl_after_replacement", default=np.nan)
        delta = numeric_series(group, "delta_vs_baseline", default=0.0)
        baseline = numeric_series(group, "baseline_month_pnl", default=np.nan)
        current_negative = baseline.lt(0.0)
        current_nonnegative = baseline.ge(0.0)
        loss_selected_count = int((risk_selected & risk_loss).sum())
        winner_selected_count = int(risk_winner.sum())
        selected_count = int(risk_selected.sum())
        loss_selection_precision = safe_rate(loss_selected_count, selected_count)
        baseline_positive_degraded_count = int((current_nonnegative & delta.lt(0.0)).sum())
        current_negative_delta = delta[current_negative]
        if int(current_negative.sum()) == 0:
            current_negative_min_delta = np.nan
            passes_current_negative_delta = True
        else:
            current_negative_min_delta = float(current_negative_delta.min())
            passes_current_negative_delta = bool(
                np.isfinite(current_negative_min_delta)
                and current_negative_min_delta >= float(min_current_negative_delta)
            )
        passes_loss_precision = bool(
            np.isfinite(loss_selection_precision)
            and loss_selection_precision >= float(min_loss_selection_precision)
        )
        passes_winner_damage = bool(winner_selected_count <= int(max_winner_trade_selected))
        passes_baseline_positive_degradation = bool(
            baseline_positive_degraded_count <= int(max_baseline_positive_degraded)
        )
        winner_violation_count = int(
            (not passes_loss_precision)
            + (not passes_winner_damage)
            + (not passes_baseline_positive_degradation)
            + (not passes_current_negative_delta)
        )
        target_success_count = int((categories == "loss_replacement_repairs_month").sum())
        target_candidate_gap_count = int(
            (categories == "loss_selected_no_supported_candidate").sum()
        )
        target_risk_gap_count = int(categories.isin(["no_risk_trade", "risk_trade_winner"]).sum())
        target_replacement_gap_count = int(categories.isin(TARGET_OUTCOME_REPLACEMENT_GAPS).sum())
        passes_target_success_count = bool(
            target_success_count >= int(min_target_outcome_success_count)
        )
        passes_target_candidate_gap = optional_max_count_pass(
            target_candidate_gap_count,
            int(max_target_candidate_gap_count),
        )
        passes_target_risk_gap = optional_max_count_pass(
            target_risk_gap_count,
            int(max_target_risk_gap_count),
        )
        passes_target_replacement_gap = optional_max_count_pass(
            target_replacement_gap_count,
            int(max_target_replacement_gap_count),
        )
        target_outcome_violation_count = int(
            (not passes_target_success_count)
            + (not passes_target_candidate_gap)
            + (not passes_target_risk_gap)
            + (not passes_target_replacement_gap)
        )
        rows.append(
            {
                **dict(zip(group_cols, keys, strict=True)),
                "target_count": int(len(group)),
                "target_outcome_success_count": target_success_count,
                "target_outcome_candidate_gap_count": target_candidate_gap_count,
                "target_outcome_risk_gap_count": target_risk_gap_count,
                "target_outcome_replacement_gap_count": target_replacement_gap_count,
                "target_outcome_winner_risk_count": int((categories == "risk_trade_winner").sum()),
                "target_outcome_no_risk_trade_count": int((categories == "no_risk_trade").sum()),
                "target_outcome_category_counts": ";".join(
                    f"{name}:{count}"
                    for name, count in categories.value_counts().sort_index().items()
                ),
                "risk_trade_selected_count": selected_count,
                "replacement_count": int(replacement.sum()),
                "loss_trade_selected_count": loss_selected_count,
                "winner_trade_selected_count": winner_selected_count,
                "loss_selection_precision": loss_selection_precision,
                "mean_month_pnl_after_replacement": float(pnl.mean()) if len(pnl) else np.nan,
                "min_month_pnl_after_replacement": float(pnl.min()) if len(pnl) else np.nan,
                "max_month_pnl_after_replacement": float(pnl.max()) if len(pnl) else np.nan,
                "mean_delta_vs_baseline": float(delta.mean()) if len(delta) else np.nan,
                "min_delta_vs_baseline": float(delta.min()) if len(delta) else np.nan,
                "positive_month_count": int(pnl.gt(0.0).sum()),
                "baseline_positive_degraded_count": baseline_positive_degraded_count,
                "baseline_positive_flipped_negative_count": int(
                    (current_nonnegative & pnl.lt(0.0)).sum()
                ),
                "current_negative_target_count": int(current_negative.sum()),
                "current_negative_mean_delta": float(current_negative_delta.mean())
                if len(current_negative_delta)
                else np.nan,
                "current_negative_min_delta": current_negative_min_delta,
                "current_negative_positive_after_count": int(
                    (current_negative & pnl.gt(0.0)).sum()
                ),
                "current_nonnegative_target_count": int(current_nonnegative.sum()),
                "current_nonnegative_mean_delta": float(delta[current_nonnegative].mean())
                if int(current_nonnegative.sum())
                else np.nan,
                "current_nonnegative_min_delta": float(delta[current_nonnegative].min())
                if int(current_nonnegative.sum())
                else np.nan,
                "mean_supported_candidate_rows": float(
                    numeric_series(group, "supported_candidate_rows", default=0.0).mean()
                ),
                "passes_loss_selection_precision": passes_loss_precision,
                "passes_winner_trade_selected": passes_winner_damage,
                "passes_baseline_positive_degradation": passes_baseline_positive_degradation,
                "passes_current_negative_delta": passes_current_negative_delta,
                "winner_damage_constraint_violation_count": winner_violation_count,
                "passes_winner_damage_constraints": bool(winner_violation_count == 0),
                "passes_target_outcome_success_count": passes_target_success_count,
                "passes_target_outcome_candidate_gap": passes_target_candidate_gap,
                "passes_target_outcome_risk_gap": passes_target_risk_gap,
                "passes_target_outcome_replacement_gap": passes_target_replacement_gap,
                "target_outcome_constraint_violation_count": target_outcome_violation_count,
                "passes_target_outcome_constraints": bool(target_outcome_violation_count == 0),
            }
        )
    return pd.DataFrame(rows).sort_values(
        [
            "passes_winner_damage_constraints",
            "passes_target_outcome_constraints",
            "winner_damage_constraint_violation_count",
            "target_outcome_constraint_violation_count",
            "passes_winner_trade_selected",
            "passes_baseline_positive_degradation",
            "passes_current_negative_delta",
            "target_outcome_success_count",
            "target_outcome_candidate_gap_count",
            "target_outcome_risk_gap_count",
            "target_outcome_replacement_gap_count",
            "loss_selection_precision",
            "mean_month_pnl_after_replacement",
            "min_month_pnl_after_replacement",
            "mean_delta_vs_baseline",
        ],
        ascending=[
            False,
            False,
            True,
            True,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            False,
            False,
            False,
            False,
        ],
    )


def annotate_target_inventory_with_evaluation(
    inventory: pd.DataFrame,
    targets: pd.DataFrame,
) -> pd.DataFrame:
    if inventory.empty:
        return inventory.copy()
    output = inventory.copy()
    if targets.empty:
        output["evaluated_by_surface"] = False
        return output
    target_cols = [
        "role",
        "family",
        "month",
        "baseline_month_pnl",
        "trade_count",
        "loss_trade_count",
        "prior_candidate_rows",
        "prior_candidate_month_count",
    ]
    available = [column for column in target_cols if column in targets.columns]
    evaluated = targets[available].copy()
    evaluated["evaluated_by_surface"] = True
    merge_cols = [column for column in ["role", "family", "month"] if column in output.columns]
    output = output.merge(
        evaluated,
        on=merge_cols,
        how="left",
        suffixes=("", "_surface"),
    )
    output["evaluated_by_surface"] = bool_series(
        output,
        "evaluated_by_surface",
        default=False,
    )
    return output


def run_diagnostics(args: argparse.Namespace) -> Path:
    config_path = resolve_path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    repair_targets = filter_repair_targets(
        pd.read_csv(resolve_path(config["repair_targets"])),
        candidate=config["candidate"],
        variant_contains=config.get("variant_contains", ""),
        entry_block_rule=config.get("entry_block_rule", ""),
    )
    current = read_current_trades(
        resolve_path(config["current_trades"]),
        candidate=config["candidate"],
        selector_variant_contains=config.get("selector_variant_contains", ""),
        entry_block_rule=config.get("entry_block_rule", ""),
    )
    current_features = add_observable_trade_features(
        current,
        large_loss_threshold=float(args.large_loss_threshold),
    )
    family_predictions = {
        str(family): resolve_path(path)
        for family, path in dict(config["family_predictions"]).items()
    }
    replacement_context_specs = parse_context_specs(args.replacement_context_specs)
    risk_context_specs = parse_risk_context_specs(args.risk_context_specs)
    risk_selectors = parse_semicolon(args.risk_selectors)
    score_modes = parse_score_modes(args.score_modes)
    calibration_min_context_counts = parse_int_grid(args.calibration_min_context_counts)
    candidate_min_prior_counts = parse_int_grid(args.candidate_min_prior_counts)
    candidate_min_prior_month_counts = parse_int_grid(args.candidate_min_prior_month_counts)
    candidate_min_prior_actual_means = parse_float_grid(args.candidate_min_prior_actual_means)
    if args.targets_inventory is not None:
        target_specs, target_inventory = resolve_inventory_target_specs(
            resolve_path(args.targets_inventory),
            min_support_sufficient_configs=int(args.inventory_min_support_sufficient_configs),
            min_metric_parents=int(args.inventory_min_metric_parents),
            max_targets=int(args.inventory_max_targets),
            target_side=str(args.inventory_target_side),
        )
    else:
        target_specs, target_inventory = resolve_target_specs(
            args.targets,
            current=current,
            repair_targets=repair_targets,
        )

    choice_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    risk_trade_frames: list[pd.DataFrame] = []
    risk_hit_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    prior_cache: dict[str, pd.DataFrame] = {}

    for role, month, target_side in target_specs:
        family = role_to_family(role)
        repair_row = select_repair_row(repair_targets, role=role, month=month)
        if repair_row is not None:
            family = str(repair_row.get("family", family))
        current_target = current_features[
            current_features["role"].astype(str).eq(role)
            & current_features["family"].astype(str).eq(family)
            & current_features["month"].astype(str).eq(month)
        ].copy()
        if current_target.empty:
            continue
        current_target = add_current_trade_repair_columns(current_target)
        month_pnl = float(numeric_series(current_target, "adjusted_pnl", default=0.0).sum())
        prediction_path = family_predictions.get(family)
        if prediction_path is None:
            raise ValueError(f"missing prediction path for family {family}")
        target_side_rows = load_extended_side_rows(
            prediction_path=prediction_path,
            family=family,
            month=month,
            config=config,
        )
        if family not in prior_cache:
            prior_cache[family] = load_family_side_rows(
                prediction_path=prediction_path,
                family=family,
                config=config,
            )
        prior_rows = prior_cache[family][prior_cache[family]["month"].astype(str).lt(month)].copy()
        prior_rows = prior_rows[
            prior_rows["candidate_stage"].astype(str).ne("non_candidate")
        ].copy()

        risk_prior_context = build_prior_context_rows(
            current_features,
            current_target,
            context_specs=risk_context_specs,
            large_loss_threshold=float(args.large_loss_threshold),
        )
        risk_target, risk_hits = add_risk_columns(current_target, risk_prior_context)
        risk_target["target_role"] = role
        risk_target["target_family"] = family
        risk_target["target_month"] = month
        risk_trade_frames.append(risk_target)
        if not risk_hits.empty:
            risk_hits["target_role"] = role
            risk_hits["target_family"] = family
            risk_hits["target_month"] = month
            risk_hit_frames.append(risk_hits)

        pool_cache: dict[tuple[str, int], pd.DataFrame] = {}
        risk_trade_by_selector: dict[str, pd.Series | None] = {}
        for risk_selector in risk_selectors:
            risk_trade_by_selector[risk_selector] = choose_trade_by_risk(
                risk_target,
                selector=risk_selector,
            )
            for calibration_min_count in calibration_min_context_counts:
                risk_trade = risk_trade_by_selector[risk_selector]
                pool = pd.DataFrame()
                candidate_rows_count = 0
                if risk_trade is not None:
                    key = (str(risk_trade["trade_id"]), int(calibration_min_count))
                    if key not in pool_cache:
                        raw_pool = candidate_pool_for_loss(
                            side_rows=target_side_rows,
                            current_trades=risk_target,
                            loss_trade=risk_trade,
                            include_non_candidate_top_score=args.include_non_candidate_top_score,
                        )
                        pool_cache[key] = add_prior_calibration(
                            raw_pool,
                            prior_rows=prior_rows,
                            context_specs=replacement_context_specs,
                            min_prior_count=int(calibration_min_count),
                        )
                        if not pool_cache[key].empty:
                            enriched = pool_cache[key].copy()
                            enriched["risk_selector"] = risk_selector
                            enriched["risk_trade_id"] = str(risk_trade["trade_id"])
                            enriched["calibration_min_context_count"] = int(calibration_min_count)
                            candidate_frames.append(enriched)
                    pool = pool_cache[key]
                    candidate_rows_count = int(len(pool))

                for candidate_min_count in candidate_min_prior_counts:
                    for candidate_min_months in candidate_min_prior_month_counts:
                        for candidate_min_actual in candidate_min_prior_actual_means:
                            supported_rows = (
                                supported_candidate_count(
                                    pool,
                                    min_prior_count=candidate_min_count,
                                    min_prior_month_count=candidate_min_months,
                                    min_prior_actual_mean=candidate_min_actual,
                                )
                                if not pool.empty
                                else 0
                            )
                            for score_mode in score_modes:
                                chosen = (
                                    choose_supported_candidate(
                                        pool,
                                        score_mode=score_mode,
                                        min_prior_count=candidate_min_count,
                                        min_prior_month_count=candidate_min_months,
                                        min_prior_actual_mean=candidate_min_actual,
                                    )
                                    if not pool.empty
                                    else None
                                )
                                choice_rows.append(
                                    selector_choice_row(
                                        role=role,
                                        family=family,
                                        month=month,
                                        month_pnl=month_pnl,
                                        risk_selector=risk_selector,
                                        risk_trade=risk_trade,
                                        replacement_score_mode=score_mode,
                                        calibration_min_context_count=calibration_min_count,
                                        candidate_min_prior_count=candidate_min_count,
                                        candidate_min_prior_month_count=candidate_min_months,
                                        candidate_min_prior_actual_mean=candidate_min_actual,
                                        candidate=chosen,
                                        candidate_rows=candidate_rows_count,
                                        supported_candidate_rows=supported_rows,
                                    )
                                )

        target_rows.append(
            {
                "role": role,
                "family": family,
                "month": month,
                "target_side": target_side,
                "baseline_month_pnl": month_pnl,
                "trade_count": int(len(current_target)),
                "loss_trade_count": int(bool_series(current_target, "is_loss_trade").sum()),
                "prior_candidate_rows": int(len(prior_rows)),
                "prior_candidate_month_count": int(prior_rows["month"].astype(str).nunique())
                if len(prior_rows)
                else 0,
                "risk_selectors": ";".join(risk_selectors),
            }
        )

    choices = add_target_outcome_columns(pd.DataFrame(choice_rows))
    summary = summarize_surface(
        choices,
        min_loss_selection_precision=float(args.min_loss_selection_precision),
        max_winner_trade_selected=int(args.max_winner_trade_selected),
        max_baseline_positive_degraded=int(args.max_baseline_positive_degraded),
        min_current_negative_delta=float(args.min_current_negative_delta),
        min_target_outcome_success_count=int(args.min_target_outcome_success_count),
        max_target_candidate_gap_count=int(args.max_target_candidate_gap_count),
        max_target_risk_gap_count=int(args.max_target_risk_gap_count),
        max_target_replacement_gap_count=int(args.max_target_replacement_gap_count),
    )
    targets = pd.DataFrame(target_rows)
    risk_trades = (
        pd.concat(risk_trade_frames, ignore_index=True, sort=False)
        if risk_trade_frames
        else pd.DataFrame()
    )
    risk_hits_out = (
        pd.concat(risk_hit_frames, ignore_index=True, sort=False)
        if risk_hit_frames
        else pd.DataFrame()
    )
    candidates = (
        pd.concat(candidate_frames, ignore_index=True, sort=False)
        if candidate_frames
        else pd.DataFrame()
    )

    run_dir = make_run_dir(resolve_path(args.output_root), args.run_label)
    target_inventory = annotate_target_inventory_with_evaluation(target_inventory, targets)
    choices.to_csv(run_dir / "support_sufficient_selector_surface_choices.csv", index=False)
    summary.to_csv(run_dir / "support_sufficient_selector_surface_summary.csv", index=False)
    targets.to_csv(run_dir / "support_sufficient_selector_surface_targets.csv", index=False)
    target_inventory.to_csv(
        run_dir / "support_sufficient_selector_surface_target_inventory.csv",
        index=False,
    )
    risk_trades.to_csv(run_dir / "support_sufficient_selector_surface_risk_trades.csv", index=False)
    risk_hits_out.to_csv(run_dir / "support_sufficient_selector_surface_risk_hits.csv", index=False)
    candidates.to_csv(run_dir / "support_sufficient_selector_surface_candidates.csv", index=False)
    meta = {
        "config": config_path,
        "targets_arg": args.targets,
        "targets_inventory": args.targets_inventory,
        "targets": target_specs,
        "target_inventory_rows": int(len(target_inventory)),
        "auto_target_values": sorted(AUTO_TARGET_VALUES),
        "inventory_min_support_sufficient_configs": args.inventory_min_support_sufficient_configs,
        "inventory_min_metric_parents": args.inventory_min_metric_parents,
        "inventory_max_targets": args.inventory_max_targets,
        "inventory_target_side": args.inventory_target_side,
        "risk_selectors": risk_selectors,
        "score_modes": score_modes,
        "replacement_context_specs": replacement_context_specs,
        "risk_context_specs": risk_context_specs,
        "calibration_min_context_counts": calibration_min_context_counts,
        "candidate_min_prior_counts": candidate_min_prior_counts,
        "candidate_min_prior_month_counts": candidate_min_prior_month_counts,
        "candidate_min_prior_actual_means": candidate_min_prior_actual_means,
        "min_loss_selection_precision": args.min_loss_selection_precision,
        "max_winner_trade_selected": args.max_winner_trade_selected,
        "max_baseline_positive_degraded": args.max_baseline_positive_degraded,
        "min_current_negative_delta": args.min_current_negative_delta,
        "min_target_outcome_success_count": args.min_target_outcome_success_count,
        "max_target_candidate_gap_count": args.max_target_candidate_gap_count,
        "max_target_risk_gap_count": args.max_target_risk_gap_count,
        "max_target_replacement_gap_count": args.max_target_replacement_gap_count,
        "large_loss_threshold": args.large_loss_threshold,
        "include_non_candidate_top_score": args.include_non_candidate_top_score,
        "note": (
            "Risk selectors use observable selected-trade features and chronological prior. "
            "oracle:worst_loss is diagnostic only. Candidate realized PnL is evaluation only."
        ),
    }
    (run_dir / "support_sufficient_selector_surface_meta.json").write_text(
        json.dumps(meta, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Support-sufficient selector surface summary:")
    summary_display_columns = [
        "risk_selector",
        "replacement_score_mode",
        "candidate_min_prior_count",
        "target_count",
        "target_outcome_success_count",
        "target_outcome_candidate_gap_count",
        "target_outcome_risk_gap_count",
        "target_outcome_replacement_gap_count",
        "loss_trade_selected_count",
        "winner_trade_selected_count",
        "loss_selection_precision",
        "baseline_positive_degraded_count",
        "current_negative_min_delta",
        "mean_month_pnl_after_replacement",
        "mean_delta_vs_baseline",
        "winner_damage_constraint_violation_count",
        "passes_winner_damage_constraints",
        "target_outcome_constraint_violation_count",
        "passes_target_outcome_constraints",
    ]
    print(
        summary[[column for column in summary_display_columns if column in summary.columns]]
        .head(int(args.print_rows))
        .to_string(index=False)
    )
    if not target_inventory.empty:
        inventory_columns = [
            "role",
            "family",
            "month",
            "target_side",
            "evaluated_by_surface",
            "month_pnl",
            "baseline_month_pnl",
            "best_month_pnl",
            "worst_month_pnl",
            "trade_count",
            "loss_trade_count",
            "support_sufficient_config_count",
            "support_limited_config_count",
            "metric_parent_count",
            "extra_long_needed",
            "extra_short_needed",
            "support_sufficient_negative_month",
            "support_limited_negative_month",
        ]
        display_columns = [column for column in inventory_columns if column in target_inventory.columns]
        print("\nTarget inventory:")
        print(target_inventory[display_columns].to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument(
        "--targets-inventory",
        type=Path,
        default=None,
        help=(
            "Use a support_negative_month_target_summary.csv file as the target source. "
            "When set, --targets is ignored."
        ),
    )
    parser.add_argument("--inventory-min-support-sufficient-configs", type=int, default=1)
    parser.add_argument("--inventory-min-metric-parents", type=int, default=1)
    parser.add_argument("--inventory-max-targets", type=int, default=0)
    parser.add_argument("--inventory-target-side", default="both")
    parser.add_argument("--replacement-context-specs", default=DEFAULT_CONTEXT_SPECS)
    parser.add_argument("--risk-context-specs", default=DEFAULT_RISK_CONTEXT_SPECS)
    parser.add_argument("--risk-selectors", default=DEFAULT_RISK_SELECTORS)
    parser.add_argument("--score-modes", default=DEFAULT_SCORE_MODES)
    parser.add_argument("--calibration-min-context-counts", default="20,50")
    parser.add_argument("--candidate-min-prior-counts", default="20,50,100")
    parser.add_argument("--candidate-min-prior-month-counts", default="1,2,3")
    parser.add_argument("--candidate-min-prior-actual-means", default="-inf,0,5,10")
    parser.add_argument("--min-loss-selection-precision", type=float, default=0.5)
    parser.add_argument("--max-winner-trade-selected", type=int, default=0)
    parser.add_argument("--max-baseline-positive-degraded", type=int, default=0)
    parser.add_argument("--min-current-negative-delta", type=float, default=0.0)
    parser.add_argument("--min-target-outcome-success-count", type=int, default=1)
    parser.add_argument("--max-target-candidate-gap-count", type=int, default=0)
    parser.add_argument(
        "--max-target-risk-gap-count",
        type=int,
        default=-1,
        help="Use -1 to leave target risk gaps unconstrained.",
    )
    parser.add_argument("--max-target-replacement-gap-count", type=int, default=0)
    parser.add_argument("--large-loss-threshold", type=float, default=-1.0)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/reports/backtests")
    parser.add_argument(
        "--run-label",
        default="entry_ev_support_sufficient_selector_surface_diagnostics",
    )
    parser.add_argument(
        "--include-non-candidate-top-score",
        action="store_true",
        help="Include holding-ok rows even if they fail strict/relaxed/one-fail gates.",
    )
    parser.add_argument("--print-rows", type=int, default=16)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
