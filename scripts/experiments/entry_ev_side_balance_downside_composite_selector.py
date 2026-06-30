#!/usr/bin/env python3
"""Composite selector for coverage, downside pressure, exit, and EV calibration."""

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

from trade_data.backtest import json_default, make_run_dir  # noqa: E402

from entry_ev_side_balance_downside_interaction import normalize_trades  # noqa: E402


def local_json_default(value: Any) -> Any:
    try:
        return json_default(value)
    except TypeError:
        pass
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_int_csv(value: str) -> list[int]:
    return [int(part) for part in parse_csv(value)]


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def read_trade_frames(paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in paths]
    if not frames:
        raise ValueError("at least one enriched side-balance downside trade CSV is required")
    return pd.concat(frames, ignore_index=True)


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(float(default)).astype(float).ne(0.0)
    normalized = series.astype(str).str.lower().str.strip()
    return normalized.isin({"true", "1", "yes", "y"})


def filter_values(frame: pd.DataFrame, column: str, values: list[str]) -> pd.DataFrame:
    if not values:
        return frame.copy()
    return frame[frame[column].astype(str).isin(values)].copy()


def ensure_composite_columns(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in [
        "adjusted_pnl",
        "prior_trade_count",
        "prior_downside_support_weight",
        "prior_downside_risk_score",
        "side_balance_downside_interaction_score",
        "side_balance_abs_signed_drift_for_trade",
        "side_balance_signed_drift_for_trade",
        "pred_taken_ev",
        "ev_overestimate_vs_realized",
        "exit_regret",
    ]:
        output[column] = numeric_series(output, column)
    for column in [
        "direction_error",
        "no_edge_entry",
        "side_balance_selected_side_overrepresented",
        "side_balance_selected_side_underrepresented",
    ]:
        output[column] = bool_series(output, column)
    return output


def cumulative_max_drawdown(values: pd.Series) -> float:
    cumulative = values.astype(float).cumsum()
    if cumulative.empty:
        return 0.0
    running_max = cumulative.cummax()
    return float((running_max - cumulative).max())


def weighted_average(values: pd.Series, weights: pd.Series) -> float:
    values = values.astype(float)
    weights = weights.astype(float)
    total_weight = float(weights.sum())
    if total_weight <= 0.0:
        return 0.0
    return float(np.average(values, weights=weights))


def feature_pressure_score(
    *,
    risk_high_share: float,
    interaction_high_share: float,
    risk_mean: float,
    prior_zero_share: float,
) -> float:
    return float(
        0.35 * risk_high_share
        + 0.30 * interaction_high_share
        + 0.20 * min(max(risk_mean, 0.0), 1.0)
        + 0.15 * prior_zero_share
    )


def composite_preflight_risk_score(
    *,
    feature_pressure: float,
    prior_zero_share: float,
    direction_error_rate: float,
    large_exit_regret_rate: float,
    no_edge_rate: float,
    ev_overestimate_component: float,
    support_gap: float,
) -> float:
    return float(
        0.20 * feature_pressure
        + 0.20 * prior_zero_share
        + 0.20 * direction_error_rate
        + 0.15 * large_exit_regret_rate
        + 0.10 * no_edge_rate
        + 0.10 * ev_overestimate_component
        + 0.05 * support_gap
    )


def summarize_role_slice(
    frame: pd.DataFrame,
    *,
    candidate: str,
    role: str,
    risk_threshold: float,
    interaction_threshold: float,
    large_exit_regret_threshold: float,
    ev_overestimate_scale: float,
) -> dict[str, Any]:
    if frame.empty:
        return {
            "candidate": candidate,
            "role": role,
            "role_present": False,
            "role_active": False,
            "role_trade_count": 0,
            "role_month_count": 0,
            "role_active_month_count": 0,
            "role_total_pnl": 0.0,
            "role_min_month_pnl": 0.0,
            "role_avg_pnl": 0.0,
            "role_win_rate": 0.0,
            "role_max_drawdown": 0.0,
            "role_long_trade_count": 0,
            "role_short_trade_count": 0,
            "role_max_side_trade_share": 0.0,
            "role_prior_zero_share": 1.0,
            "role_prior_support_mean": 0.0,
            "role_support_gap": 1.0,
            "role_feature_pressure_score": 1.0,
            "role_risk_high_share": 1.0,
            "role_interaction_high_share": 1.0,
            "role_risk_mean": 1.0,
            "role_interaction_mean": 1.0,
            "role_abs_drift_mean": 0.0,
            "role_direction_error_rate": 1.0,
            "role_no_edge_rate": 1.0,
            "role_large_exit_regret_rate": 1.0,
            "role_exit_regret_mean": 0.0,
            "role_pred_taken_ev_mean": 0.0,
            "role_ev_overestimate_mean": 0.0,
            "role_ev_overestimate_component": 1.0,
            "role_composite_preflight_risk_score": 1.0,
        }

    ordered = frame.sort_values("entry_decision_timestamp")
    pnl = ordered["adjusted_pnl"].astype(float)
    direction = ordered["direction"].astype(str).str.lower()
    risk = ordered["prior_downside_risk_score"].astype(float)
    interaction = ordered["side_balance_downside_interaction_score"].astype(float)
    prior_trade_count = ordered["prior_trade_count"].astype(float)
    support = ordered["prior_downside_support_weight"].astype(float)
    exit_regret = ordered["exit_regret"].astype(float)
    ev_overestimate = ordered["ev_overestimate_vs_realized"].astype(float)
    ev_overestimate_positive = ev_overestimate.clip(lower=0.0)
    overestimate_component = float(
        np.clip(ev_overestimate_positive / ev_overestimate_scale, 0.0, 1.0).mean()
    )
    risk_high_share = float((risk >= risk_threshold).mean())
    interaction_high_share = float((interaction >= interaction_threshold).mean())
    risk_mean = float(risk.mean())
    prior_zero_share = float((prior_trade_count <= 0.0).mean())
    support_mean = float(support.mean())
    feature_pressure = feature_pressure_score(
        risk_high_share=risk_high_share,
        interaction_high_share=interaction_high_share,
        risk_mean=risk_mean,
        prior_zero_share=prior_zero_share,
    )
    direction_error_rate = float(ordered["direction_error"].astype(bool).mean())
    no_edge_rate = float(ordered["no_edge_entry"].astype(bool).mean())
    large_exit_regret_rate = float((exit_regret >= large_exit_regret_threshold).mean())
    support_gap = float(1.0 - np.clip(support_mean, 0.0, 1.0))
    composite_risk = composite_preflight_risk_score(
        feature_pressure=feature_pressure,
        prior_zero_share=prior_zero_share,
        direction_error_rate=direction_error_rate,
        large_exit_regret_rate=large_exit_regret_rate,
        no_edge_rate=no_edge_rate,
        ev_overestimate_component=overestimate_component,
        support_gap=support_gap,
    )
    month_pnl = ordered.groupby("month", dropna=False)["adjusted_pnl"].sum()
    trade_count = int(len(ordered))
    long_count = int(direction.eq("long").sum())
    short_count = int(direction.eq("short").sum())
    return {
        "candidate": candidate,
        "role": role,
        "role_present": True,
        "role_active": bool(trade_count > 0),
        "role_trade_count": trade_count,
        "role_month_count": int(ordered["month"].nunique()),
        "role_active_month_count": int(month_pnl.ne(0.0).sum()),
        "role_total_pnl": float(pnl.sum()),
        "role_min_month_pnl": float(month_pnl.min()) if not month_pnl.empty else 0.0,
        "role_avg_pnl": float(pnl.mean()),
        "role_win_rate": float(pnl.gt(0.0).mean()),
        "role_max_drawdown": cumulative_max_drawdown(pnl),
        "role_long_trade_count": long_count,
        "role_short_trade_count": short_count,
        "role_max_side_trade_share": float(max(long_count, short_count) / trade_count),
        "role_prior_zero_share": prior_zero_share,
        "role_prior_support_mean": support_mean,
        "role_support_gap": support_gap,
        "role_feature_pressure_score": feature_pressure,
        "role_risk_high_share": risk_high_share,
        "role_interaction_high_share": interaction_high_share,
        "role_risk_mean": risk_mean,
        "role_interaction_mean": float(interaction.mean()),
        "role_abs_drift_mean": float(
            ordered["side_balance_abs_signed_drift_for_trade"].astype(float).mean()
        ),
        "role_direction_error_rate": direction_error_rate,
        "role_no_edge_rate": no_edge_rate,
        "role_large_exit_regret_rate": large_exit_regret_rate,
        "role_exit_regret_mean": float(exit_regret.mean()),
        "role_pred_taken_ev_mean": float(ordered["pred_taken_ev"].astype(float).mean()),
        "role_ev_overestimate_mean": float(ev_overestimate.mean()),
        "role_ev_overestimate_component": overestimate_component,
        "role_composite_preflight_risk_score": composite_risk,
    }


def summarize_required_roles(
    frame: pd.DataFrame,
    *,
    required_roles: list[str],
    risk_threshold: float,
    interaction_threshold: float,
    large_exit_regret_threshold: float,
    ev_overestimate_scale: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    role_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for candidate, candidate_frame in frame.groupby("candidate", dropna=False):
        candidate_role_rows: list[dict[str, Any]] = []
        for role in required_roles:
            role_frame = candidate_frame[candidate_frame["role"].eq(role)]
            role_row = summarize_role_slice(
                role_frame,
                candidate=candidate,
                role=role,
                risk_threshold=risk_threshold,
                interaction_threshold=interaction_threshold,
                large_exit_regret_threshold=large_exit_regret_threshold,
                ev_overestimate_scale=ev_overestimate_scale,
            )
            candidate_role_rows.append(role_row)
            role_rows.append(role_row)
        role_summary = pd.DataFrame(candidate_role_rows)
        active_roles = role_summary[role_summary["role_active"]]
        missing_roles = role_summary[~role_summary["role_present"]]["role"].astype(str).tolist()
        inactive_roles = role_summary[~role_summary["role_active"]]["role"].astype(str).tolist()
        role_trade_count = role_summary["role_trade_count"].astype(float)
        total_trade_count = int(role_trade_count.sum())
        long_count = int(role_summary["role_long_trade_count"].sum())
        short_count = int(role_summary["role_short_trade_count"].sum())
        weights = role_trade_count
        candidate_rows.append(
            {
                "candidate": candidate,
                "required_role_count": len(required_roles),
                "present_required_role_count": int(role_summary["role_present"].sum()),
                "active_required_role_count": int(role_summary["role_active"].sum()),
                "missing_required_roles": ",".join(missing_roles),
                "inactive_required_roles": ",".join(inactive_roles),
                "total_pnl": float(role_summary["role_total_pnl"].sum()),
                "min_required_role_total_pnl": float(role_summary["role_total_pnl"].min()),
                "min_active_role_total_pnl": (
                    float(active_roles["role_total_pnl"].min()) if not active_roles.empty else 0.0
                ),
                "min_required_month_pnl": float(role_summary["role_min_month_pnl"].min()),
                "trade_count": total_trade_count,
                "min_required_role_trades": int(role_trade_count.min()),
                "min_active_role_trades": (
                    int(active_roles["role_trade_count"].min()) if not active_roles.empty else 0
                ),
                "long_trade_count": long_count,
                "short_trade_count": short_count,
                "max_side_trade_share": (
                    float(max(long_count, short_count) / total_trade_count)
                    if total_trade_count
                    else 0.0
                ),
                "max_required_role_prior_zero_share": float(
                    role_summary["role_prior_zero_share"].max()
                ),
                "min_required_role_prior_support_mean": float(
                    role_summary["role_prior_support_mean"].min()
                ),
                "max_required_role_feature_pressure_score": float(
                    role_summary["role_feature_pressure_score"].max()
                ),
                "max_required_role_composite_preflight_risk_score": float(
                    role_summary["role_composite_preflight_risk_score"].max()
                ),
                "max_required_role_direction_error_rate": float(
                    role_summary["role_direction_error_rate"].max()
                ),
                "max_required_role_large_exit_regret_rate": float(
                    role_summary["role_large_exit_regret_rate"].max()
                ),
                "max_required_role_ev_overestimate_component": float(
                    role_summary["role_ev_overestimate_component"].max()
                ),
                "avg_required_role_composite_preflight_risk_score": weighted_average(
                    role_summary["role_composite_preflight_risk_score"],
                    weights,
                ),
                "avg_required_role_feature_pressure_score": weighted_average(
                    role_summary["role_feature_pressure_score"],
                    weights,
                ),
                "avg_required_role_direction_error_rate": weighted_average(
                    role_summary["role_direction_error_rate"],
                    weights,
                ),
                "avg_required_role_large_exit_regret_rate": weighted_average(
                    role_summary["role_large_exit_regret_rate"],
                    weights,
                ),
                "avg_required_role_ev_overestimate_component": weighted_average(
                    role_summary["role_ev_overestimate_component"],
                    weights,
                ),
                "pred_taken_ev_mean": weighted_average(
                    role_summary["role_pred_taken_ev_mean"],
                    weights,
                ),
                "ev_overestimate_mean": weighted_average(
                    role_summary["role_ev_overestimate_mean"],
                    weights,
                ),
            }
        )
    return (
        pd.DataFrame(candidate_rows).sort_values(
            [
                "active_required_role_count",
                "min_required_role_total_pnl",
                "total_pnl",
                "max_required_role_composite_preflight_risk_score",
            ],
            ascending=[False, False, False, True],
        ).reset_index(drop=True),
        pd.DataFrame(role_rows).sort_values(["candidate", "role"]).reset_index(drop=True),
    )


def candidate_blockers(
    row: pd.Series,
    *,
    required_role_count: int,
    min_active_required_roles: int,
    min_required_role_trades: int,
    min_total_pnl: float,
    min_required_role_total_pnl: float,
    min_required_month_pnl: float,
    max_side_trade_share: float,
    max_required_role_prior_zero_share: float,
    min_required_role_prior_support_mean: float,
    max_required_role_feature_pressure_score: float,
    max_required_role_composite_preflight_risk_score: float,
    max_required_role_direction_error_rate: float,
    max_required_role_large_exit_regret_rate: float,
    max_required_role_ev_overestimate_component: float,
) -> list[str]:
    checks = [
        ("required_roles_missing", row["present_required_role_count"] >= required_role_count),
        ("active_required_roles_low", row["active_required_role_count"] >= min_active_required_roles),
        ("required_role_trades_low", row["min_required_role_trades"] >= min_required_role_trades),
        ("total_pnl_below_floor", row["total_pnl"] >= min_total_pnl),
        (
            "required_role_total_pnl_below_floor",
            row["min_required_role_total_pnl"] >= min_required_role_total_pnl,
        ),
        (
            "required_month_pnl_below_floor",
            row["min_required_month_pnl"] >= min_required_month_pnl,
        ),
        ("side_share_high", row["max_side_trade_share"] <= max_side_trade_share),
        (
            "required_role_prior_zero_high",
            row["max_required_role_prior_zero_share"] <= max_required_role_prior_zero_share,
        ),
        (
            "required_role_prior_support_low",
            row["min_required_role_prior_support_mean"] >= min_required_role_prior_support_mean,
        ),
        (
            "required_role_feature_pressure_high",
            row["max_required_role_feature_pressure_score"]
            <= max_required_role_feature_pressure_score,
        ),
        (
            "required_role_composite_risk_high",
            row["max_required_role_composite_preflight_risk_score"]
            <= max_required_role_composite_preflight_risk_score,
        ),
        (
            "required_role_direction_error_high",
            row["max_required_role_direction_error_rate"]
            <= max_required_role_direction_error_rate,
        ),
        (
            "required_role_exit_regret_high",
            row["max_required_role_large_exit_regret_rate"]
            <= max_required_role_large_exit_regret_rate,
        ),
        (
            "required_role_ev_overestimate_high",
            row["max_required_role_ev_overestimate_component"]
            <= max_required_role_ev_overestimate_component,
        ),
    ]
    return [label for label, ok in checks if not bool(ok)]


def apply_composite_gates(
    summary: pd.DataFrame,
    *,
    required_role_count: int,
    min_active_required_roles: int,
    min_required_role_trades: int,
    min_total_pnl: float,
    min_required_role_total_pnl: float,
    min_required_month_pnl: float,
    max_side_trade_share: float,
    max_required_role_prior_zero_share: float,
    min_required_role_prior_support_mean: float,
    max_required_role_feature_pressure_score: float,
    max_required_role_composite_preflight_risk_score: float,
    max_required_role_direction_error_rate: float,
    max_required_role_large_exit_regret_rate: float,
    max_required_role_ev_overestimate_component: float,
) -> pd.DataFrame:
    result = summary.copy()
    blockers: list[str] = []
    eligible: list[bool] = []
    for _, row in result.iterrows():
        row_blockers = candidate_blockers(
            row,
            required_role_count=required_role_count,
            min_active_required_roles=min_active_required_roles,
            min_required_role_trades=min_required_role_trades,
            min_total_pnl=min_total_pnl,
            min_required_role_total_pnl=min_required_role_total_pnl,
            min_required_month_pnl=min_required_month_pnl,
            max_side_trade_share=max_side_trade_share,
            max_required_role_prior_zero_share=max_required_role_prior_zero_share,
            min_required_role_prior_support_mean=min_required_role_prior_support_mean,
            max_required_role_feature_pressure_score=max_required_role_feature_pressure_score,
            max_required_role_composite_preflight_risk_score=(
                max_required_role_composite_preflight_risk_score
            ),
            max_required_role_direction_error_rate=max_required_role_direction_error_rate,
            max_required_role_large_exit_regret_rate=max_required_role_large_exit_regret_rate,
            max_required_role_ev_overestimate_component=(
                max_required_role_ev_overestimate_component
            ),
        )
        blockers.append(";".join(row_blockers))
        eligible.append(not row_blockers)
    result["eligible"] = eligible
    result["blockers"] = blockers
    return result.sort_values(
        [
            "eligible",
            "min_required_role_total_pnl",
            "total_pnl",
            "min_required_month_pnl",
            "max_required_role_composite_preflight_risk_score",
        ],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)


def select_policy(gated: pd.DataFrame) -> dict[str, Any]:
    eligible = gated[gated["eligible"]]
    if eligible.empty:
        return {
            "selected": "no_trade",
            "reason": "no candidate passed composite coverage/calibration gates",
        }
    selected = eligible.iloc[0].to_dict()
    selected["selected"] = "policy"
    selected["reason"] = "best eligible candidate after composite preflight"
    return selected


def build_blocker_summary(gated: pd.DataFrame) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for blockers in gated["blockers"].fillna("").astype(str):
        for blocker in [part for part in blockers.split(";") if part]:
            counts[blocker] = counts.get(blocker, 0) + 1
    return pd.DataFrame(
        [{"blocker": blocker, "candidate_count": count} for blocker, count in counts.items()]
    ).sort_values(["candidate_count", "blocker"], ascending=[False, True])


def summarize_gate_sensitivity(
    summary: pd.DataFrame,
    args: argparse.Namespace,
    *,
    required_role_count: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for active_roles in parse_int_csv(args.min_active_required_roles_grid):
        for role_trades in parse_int_csv(args.min_required_role_trades_grid):
            for prior_zero in parse_float_csv(args.max_required_role_prior_zero_share_grid):
                for support in parse_float_csv(args.min_required_role_prior_support_mean_grid):
                    for pressure in parse_float_csv(
                        args.max_required_role_feature_pressure_score_grid
                    ):
                        for composite in parse_float_csv(
                            args.max_required_role_composite_preflight_risk_score_grid
                        ):
                            for direction_error in parse_float_csv(
                                args.max_required_role_direction_error_rate_grid
                            ):
                                for exit_regret in parse_float_csv(
                                    args.max_required_role_large_exit_regret_rate_grid
                                ):
                                    gated = apply_composite_gates(
                                        summary,
                                        required_role_count=required_role_count,
                                        min_active_required_roles=active_roles,
                                        min_required_role_trades=role_trades,
                                        min_total_pnl=args.min_total_pnl,
                                        min_required_role_total_pnl=(
                                            args.min_required_role_total_pnl
                                        ),
                                        min_required_month_pnl=args.min_required_month_pnl,
                                        max_side_trade_share=args.max_side_trade_share,
                                        max_required_role_prior_zero_share=prior_zero,
                                        min_required_role_prior_support_mean=support,
                                        max_required_role_feature_pressure_score=pressure,
                                        max_required_role_composite_preflight_risk_score=(
                                            composite
                                        ),
                                        max_required_role_direction_error_rate=direction_error,
                                        max_required_role_large_exit_regret_rate=exit_regret,
                                        max_required_role_ev_overestimate_component=(
                                            args.max_required_role_ev_overestimate_component
                                        ),
                                    )
                                    selection = select_policy(gated)
                                    row = {
                                        "min_active_required_roles": active_roles,
                                        "min_required_role_trades": role_trades,
                                        "max_required_role_prior_zero_share": prior_zero,
                                        "min_required_role_prior_support_mean": support,
                                        "max_required_role_feature_pressure_score": pressure,
                                        "max_required_role_composite_preflight_risk_score": (
                                            composite
                                        ),
                                        "max_required_role_direction_error_rate": (
                                            direction_error
                                        ),
                                        "max_required_role_large_exit_regret_rate": exit_regret,
                                        "eligible_candidate_count": int(gated["eligible"].sum()),
                                        "selected": selection["selected"],
                                        "reason": selection["reason"],
                                        "candidate": "",
                                        "total_pnl": np.nan,
                                        "min_required_role_total_pnl": np.nan,
                                        "min_required_month_pnl": np.nan,
                                        "trade_count": 0,
                                        "active_required_role_count": 0,
                                        "max_required_role_composite_preflight_risk_score_value": (
                                            np.nan
                                        ),
                                        "max_required_role_prior_zero_share_value": np.nan,
                                        "max_required_role_feature_pressure_score_value": np.nan,
                                    }
                                    if selection["selected"] == "policy":
                                        row.update(
                                            {
                                                "candidate": selection.get("candidate", ""),
                                                "total_pnl": selection.get("total_pnl", np.nan),
                                                "min_required_role_total_pnl": selection.get(
                                                    "min_required_role_total_pnl",
                                                    np.nan,
                                                ),
                                                "min_required_month_pnl": selection.get(
                                                    "min_required_month_pnl",
                                                    np.nan,
                                                ),
                                                "trade_count": selection.get("trade_count", 0),
                                                "active_required_role_count": selection.get(
                                                    "active_required_role_count",
                                                    0,
                                                ),
                                                "max_required_role_composite_preflight_risk_score_value": selection.get(
                                                    "max_required_role_composite_preflight_risk_score",
                                                    np.nan,
                                                ),
                                                "max_required_role_prior_zero_share_value": (
                                                    selection.get(
                                                        "max_required_role_prior_zero_share",
                                                        np.nan,
                                                    )
                                                ),
                                                "max_required_role_feature_pressure_score_value": (
                                                    selection.get(
                                                        "max_required_role_feature_pressure_score",
                                                        np.nan,
                                                    )
                                                ),
                                            }
                                        )
                                    rows.append(row)
    return pd.DataFrame(rows).sort_values(
        [
            "selected",
            "min_required_role_total_pnl",
            "total_pnl",
            "eligible_candidate_count",
            "max_required_role_composite_preflight_risk_score_value",
        ],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)


def build_diagnostics(args: argparse.Namespace) -> Path:
    required_roles = parse_csv(args.required_roles)
    if not required_roles:
        raise ValueError("--required-roles must not be empty")

    trades = ensure_composite_columns(normalize_trades(read_trade_frames(args.trades)))
    trades = filter_values(trades, "role", required_roles)
    trades = filter_values(trades, "candidate", parse_csv(args.candidates))
    if trades.empty:
        raise ValueError("no trades remain after filters")

    candidate_summary, role_summary = summarize_required_roles(
        trades,
        required_roles=required_roles,
        risk_threshold=args.risk_threshold,
        interaction_threshold=args.interaction_threshold,
        large_exit_regret_threshold=args.large_exit_regret_threshold,
        ev_overestimate_scale=args.ev_overestimate_scale,
    )
    gated = apply_composite_gates(
        candidate_summary,
        required_role_count=len(required_roles),
        min_active_required_roles=args.min_active_required_roles,
        min_required_role_trades=args.min_required_role_trades,
        min_total_pnl=args.min_total_pnl,
        min_required_role_total_pnl=args.min_required_role_total_pnl,
        min_required_month_pnl=args.min_required_month_pnl,
        max_side_trade_share=args.max_side_trade_share,
        max_required_role_prior_zero_share=args.max_required_role_prior_zero_share,
        min_required_role_prior_support_mean=args.min_required_role_prior_support_mean,
        max_required_role_feature_pressure_score=args.max_required_role_feature_pressure_score,
        max_required_role_composite_preflight_risk_score=(
            args.max_required_role_composite_preflight_risk_score
        ),
        max_required_role_direction_error_rate=args.max_required_role_direction_error_rate,
        max_required_role_large_exit_regret_rate=(
            args.max_required_role_large_exit_regret_rate
        ),
        max_required_role_ev_overestimate_component=(
            args.max_required_role_ev_overestimate_component
        ),
    )
    selection = select_policy(gated)
    blocker_summary = build_blocker_summary(gated)
    sensitivity = summarize_gate_sensitivity(
        candidate_summary,
        args,
        required_role_count=len(required_roles),
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    candidate_summary.to_csv(run_dir / "composite_candidate_summary.csv", index=False)
    role_summary.to_csv(run_dir / "composite_role_summary.csv", index=False)
    gated.to_csv(run_dir / "composite_candidate_selection.csv", index=False)
    blocker_summary.to_csv(run_dir / "blocker_summary.csv", index=False)
    sensitivity.to_csv(run_dir / "composite_gate_sensitivity.csv", index=False)
    (run_dir / "selected_policy.json").write_text(
        json.dumps(selection, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    config = {
        "trades": args.trades,
        "required_roles": required_roles,
        "candidates": parse_csv(args.candidates),
        "risk_threshold": args.risk_threshold,
        "interaction_threshold": args.interaction_threshold,
        "large_exit_regret_threshold": args.large_exit_regret_threshold,
        "ev_overestimate_scale": args.ev_overestimate_scale,
        "min_active_required_roles": args.min_active_required_roles,
        "min_required_role_trades": args.min_required_role_trades,
        "min_total_pnl": args.min_total_pnl,
        "min_required_role_total_pnl": args.min_required_role_total_pnl,
        "min_required_month_pnl": args.min_required_month_pnl,
        "max_side_trade_share": args.max_side_trade_share,
        "max_required_role_prior_zero_share": args.max_required_role_prior_zero_share,
        "min_required_role_prior_support_mean": args.min_required_role_prior_support_mean,
        "max_required_role_feature_pressure_score": (
            args.max_required_role_feature_pressure_score
        ),
        "max_required_role_composite_preflight_risk_score": (
            args.max_required_role_composite_preflight_risk_score
        ),
        "max_required_role_direction_error_rate": (
            args.max_required_role_direction_error_rate
        ),
        "max_required_role_large_exit_regret_rate": (
            args.max_required_role_large_exit_regret_rate
        ),
        "max_required_role_ev_overestimate_component": (
            args.max_required_role_ev_overestimate_component
        ),
        "min_active_required_roles_grid": parse_int_csv(args.min_active_required_roles_grid),
        "min_required_role_trades_grid": parse_int_csv(args.min_required_role_trades_grid),
        "max_required_role_prior_zero_share_grid": parse_float_csv(
            args.max_required_role_prior_zero_share_grid
        ),
        "min_required_role_prior_support_mean_grid": parse_float_csv(
            args.min_required_role_prior_support_mean_grid
        ),
        "max_required_role_feature_pressure_score_grid": parse_float_csv(
            args.max_required_role_feature_pressure_score_grid
        ),
        "max_required_role_composite_preflight_risk_score_grid": parse_float_csv(
            args.max_required_role_composite_preflight_risk_score_grid
        ),
        "max_required_role_direction_error_rate_grid": parse_float_csv(
            args.max_required_role_direction_error_rate_grid
        ),
        "max_required_role_large_exit_regret_rate_grid": parse_float_csv(
            args.max_required_role_large_exit_regret_rate_grid
        ),
        "note": (
            "selection uses validation trades only; EV overestimate and realized PnL floors are "
            "validation calibration diagnostics, not model-time input features"
        ),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Composite candidate selection:")
    print(
        gated[
            [
                "candidate",
                "eligible",
                "blockers",
                "active_required_role_count",
                "missing_required_roles",
                "total_pnl",
                "min_required_role_total_pnl",
                "min_required_month_pnl",
                "trade_count",
                "max_required_role_prior_zero_share",
                "max_required_role_feature_pressure_score",
                "max_required_role_composite_preflight_risk_score",
                "max_required_role_direction_error_rate",
                "max_required_role_large_exit_regret_rate",
                "max_required_role_ev_overestimate_component",
            ]
        ]
        .head(args.top_n)
        .to_string(index=False)
    )
    print(f"selected: {selection['selected']} ({selection['reason']})")
    print("\nComposite gate sensitivity:")
    print(sensitivity.head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=Path, action="append", required=True)
    parser.add_argument("--required-roles", required=True)
    parser.add_argument("--candidates", default="")
    parser.add_argument("--risk-threshold", type=float, default=0.20)
    parser.add_argument("--interaction-threshold", type=float, default=0.005)
    parser.add_argument("--large-exit-regret-threshold", type=float, default=10.0)
    parser.add_argument("--ev-overestimate-scale", type=float, default=15.0)
    parser.add_argument("--min-active-required-roles", type=int, default=3)
    parser.add_argument("--min-required-role-trades", type=int, default=1)
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-required-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-required-month-pnl", type=float, default=0.0)
    parser.add_argument("--max-side-trade-share", type=float, default=float("inf"))
    parser.add_argument("--max-required-role-prior-zero-share", type=float, default=0.75)
    parser.add_argument("--min-required-role-prior-support-mean", type=float, default=0.0)
    parser.add_argument("--max-required-role-feature-pressure-score", type=float, default=0.50)
    parser.add_argument(
        "--max-required-role-composite-preflight-risk-score",
        type=float,
        default=0.50,
    )
    parser.add_argument("--max-required-role-direction-error-rate", type=float, default=0.75)
    parser.add_argument(
        "--max-required-role-large-exit-regret-rate",
        type=float,
        default=0.75,
    )
    parser.add_argument(
        "--max-required-role-ev-overestimate-component",
        type=float,
        default=1.0,
    )
    parser.add_argument("--min-active-required-roles-grid", default="3,2")
    parser.add_argument("--min-required-role-trades-grid", default="1")
    parser.add_argument("--max-required-role-prior-zero-share-grid", default="0.75,0.95,inf")
    parser.add_argument("--min-required-role-prior-support-mean-grid", default="0.00,0.10")
    parser.add_argument("--max-required-role-feature-pressure-score-grid", default="0.50,inf")
    parser.add_argument(
        "--max-required-role-composite-preflight-risk-score-grid",
        default="0.50,0.65,inf",
    )
    parser.add_argument("--max-required-role-direction-error-rate-grid", default="0.75,inf")
    parser.add_argument(
        "--max-required-role-large-exit-regret-rate-grid",
        default="0.75,inf",
    )
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument(
        "--label",
        default="entry_ev_side_balance_downside_composite_selector",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
