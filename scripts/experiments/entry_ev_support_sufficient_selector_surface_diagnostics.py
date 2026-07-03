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


def summarize_surface(choices: pd.DataFrame) -> pd.DataFrame:
    if choices.empty:
        return pd.DataFrame()
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
        pnl = numeric_series(group, "month_pnl_after_replacement", default=np.nan)
        delta = numeric_series(group, "delta_vs_baseline", default=0.0)
        rows.append(
            {
                **dict(zip(group_cols, keys, strict=True)),
                "target_count": int(len(group)),
                "risk_trade_selected_count": int(risk_selected.sum()),
                "replacement_count": int(replacement.sum()),
                "loss_trade_selected_count": int((risk_selected & risk_loss).sum()),
                "winner_trade_selected_count": int((risk_selected & ~risk_loss).sum()),
                "mean_month_pnl_after_replacement": float(pnl.mean()) if len(pnl) else np.nan,
                "min_month_pnl_after_replacement": float(pnl.min()) if len(pnl) else np.nan,
                "max_month_pnl_after_replacement": float(pnl.max()) if len(pnl) else np.nan,
                "mean_delta_vs_baseline": float(delta.mean()) if len(delta) else np.nan,
                "min_delta_vs_baseline": float(delta.min()) if len(delta) else np.nan,
                "positive_month_count": int(pnl.gt(0.0).sum()),
                "mean_supported_candidate_rows": float(
                    numeric_series(group, "supported_candidate_rows", default=0.0).mean()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        [
            "mean_month_pnl_after_replacement",
            "min_month_pnl_after_replacement",
            "mean_delta_vs_baseline",
        ],
        ascending=[False, False, False],
    )


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

    choice_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    risk_trade_frames: list[pd.DataFrame] = []
    risk_hit_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    prior_cache: dict[str, pd.DataFrame] = {}

    for role, month, target_side in parse_targets(args.targets):
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

    choices = pd.DataFrame(choice_rows)
    summary = summarize_surface(choices)
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
    choices.to_csv(run_dir / "support_sufficient_selector_surface_choices.csv", index=False)
    summary.to_csv(run_dir / "support_sufficient_selector_surface_summary.csv", index=False)
    targets.to_csv(run_dir / "support_sufficient_selector_surface_targets.csv", index=False)
    risk_trades.to_csv(run_dir / "support_sufficient_selector_surface_risk_trades.csv", index=False)
    risk_hits_out.to_csv(run_dir / "support_sufficient_selector_surface_risk_hits.csv", index=False)
    candidates.to_csv(run_dir / "support_sufficient_selector_surface_candidates.csv", index=False)
    meta = {
        "config": config_path,
        "targets": parse_targets(args.targets),
        "risk_selectors": risk_selectors,
        "score_modes": score_modes,
        "replacement_context_specs": replacement_context_specs,
        "risk_context_specs": risk_context_specs,
        "calibration_min_context_counts": calibration_min_context_counts,
        "candidate_min_prior_counts": candidate_min_prior_counts,
        "candidate_min_prior_month_counts": candidate_min_prior_month_counts,
        "candidate_min_prior_actual_means": candidate_min_prior_actual_means,
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
    print(summary.head(int(args.print_rows)).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--replacement-context-specs", default=DEFAULT_CONTEXT_SPECS)
    parser.add_argument("--risk-context-specs", default=DEFAULT_RISK_CONTEXT_SPECS)
    parser.add_argument("--risk-selectors", default=DEFAULT_RISK_SELECTORS)
    parser.add_argument("--score-modes", default=DEFAULT_SCORE_MODES)
    parser.add_argument("--calibration-min-context-counts", default="20,50")
    parser.add_argument("--candidate-min-prior-counts", default="20,50,100")
    parser.add_argument("--candidate-min-prior-month-counts", default="1,2,3")
    parser.add_argument("--candidate-min-prior-actual-means", default="-inf,0,5,10")
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
