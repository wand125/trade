#!/usr/bin/env python3
"""Evaluate EV-overestimate target risk as a NoTrade-first selector feature."""

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

from entry_ev_component_target_calibration import (  # noqa: E402
    chronological_month_predictions,
    normalize_targets,
)


DEFAULT_TARGET = "executable_ev_overestimate_target"


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


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def read_component_frame(path: Path, *, target: str, group_columns: list[str]) -> pd.DataFrame:
    frame = normalize_targets(
        pd.read_csv(path),
        targets=[target],
        group_columns=group_columns,
    )
    required = {
        "direction",
        "entry_decision_timestamp",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"component target frame missing columns: {', '.join(missing)}")
    frame["direction"] = frame["direction"].astype(str).str.lower()
    frame["entry_decision_timestamp"] = pd.to_datetime(
        frame["entry_decision_timestamp"],
        utc=True,
    )
    return frame


def build_chronological_ev_risk(
    frame: pd.DataFrame,
    *,
    target: str,
    group_columns: list[str],
    prior_strength: float,
    min_group_support: int,
) -> pd.DataFrame:
    predictions, _ = chronological_month_predictions(
        frame,
        targets=[target],
        group_columns=group_columns,
        prior_strength=prior_strength,
        min_group_support=min_group_support,
    )
    predictions = predictions[predictions["target"].eq(target)].copy()
    predictions = predictions.rename(
        columns={
            "predicted_target_rate": "predicted_ev_overestimate_risk",
            "prediction_source": "ev_overestimate_prediction_source",
            "prediction_support": "ev_overestimate_prediction_support",
        }
    )
    predictions["ev_overestimate_prediction_available"] = predictions[
        "predicted_ev_overestimate_risk"
    ].notna() & np.isfinite(predictions["predicted_ev_overestimate_risk"].astype(float))
    return predictions


def cumulative_max_drawdown(values: pd.Series) -> float:
    cumulative = values.astype(float).cumsum()
    if cumulative.empty:
        return 0.0
    running_max = cumulative.cummax()
    return float((running_max - cumulative).max())


def weighted_average(values: pd.Series, weights: pd.Series) -> float:
    values = values.astype(float)
    weights = weights.astype(float)
    valid = values.notna() & np.isfinite(values) & weights.gt(0.0)
    if not bool(valid.any()):
        return float("nan")
    return float(np.average(values[valid], weights=weights[valid]))


def summarize_trade_slice(
    frame: pd.DataFrame,
    *,
    target: str,
    risk_threshold: float,
) -> dict[str, Any]:
    if frame.empty:
        return {
            "trade_count": 0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
        }
    ordered = frame.sort_values("entry_decision_timestamp")
    pnl = ordered["adjusted_pnl"].astype(float)
    direction = ordered["direction"].astype(str).str.lower()
    target_values = ordered[target].astype(bool)
    risk = ordered["predicted_ev_overestimate_risk"].astype(float)
    available = ordered["ev_overestimate_prediction_available"].astype(bool)
    source = ordered["ev_overestimate_prediction_source"].astype(str)
    trade_count = int(len(ordered))
    long_count = int(direction.eq("long").sum())
    short_count = int(direction.eq("short").sum())
    high_risk = available & risk.ge(risk_threshold)
    predicted_count = int(available.sum())
    no_prior = source.eq("no_prior")
    bucket = source.eq("bucket")
    global_fallback = source.eq("global")
    return {
        "trade_count": trade_count,
        "total_pnl": float(pnl.sum()),
        "avg_pnl": float(pnl.mean()),
        "win_rate": float(pnl.gt(0.0).mean()),
        "max_drawdown": cumulative_max_drawdown(pnl),
        "long_trade_count": long_count,
        "short_trade_count": short_count,
        "max_side_trade_share": float(max(long_count, short_count) / trade_count),
        "target_rate": float(target_values.mean()),
        "target_true_pnl": float(pnl.where(target_values, 0.0).sum()),
        "target_false_pnl": float(pnl.where(~target_values, 0.0).sum()),
        "prediction_count": predicted_count,
        "prediction_coverage": float(predicted_count / trade_count),
        "predicted_risk_mean": float(risk[available].mean()) if predicted_count else float("nan"),
        "predicted_risk_p75": float(risk[available].quantile(0.75))
        if predicted_count
        else float("nan"),
        "predicted_risk_p90": float(risk[available].quantile(0.90))
        if predicted_count
        else float("nan"),
        "high_risk_share": float(high_risk.mean()),
        "high_risk_share_predicted": float(risk[available].ge(risk_threshold).mean())
        if predicted_count
        else float("nan"),
        "high_risk_pnl": float(pnl.where(high_risk, 0.0).sum()),
        "no_prior_share": float(no_prior.mean()),
        "bucket_prediction_share": float(bucket.mean()),
        "global_prediction_share": float(global_fallback.mean()),
        "mean_prediction_support": float(
            ordered["ev_overestimate_prediction_support"].astype(float).mean()
        ),
    }


def summarize_role_months(
    frame: pd.DataFrame,
    *,
    target: str,
    risk_threshold: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (candidate, role, month), group in frame.groupby(
        ["candidate", "role", "month"],
        dropna=False,
    ):
        row = {"candidate": candidate, "role": role, "month": month}
        row.update(
            summarize_trade_slice(
                group,
                target=target,
                risk_threshold=risk_threshold,
            )
        )
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["candidate", "role", "month"]).reset_index(drop=True)


def summarize_candidates(role_month: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for candidate, group in role_month.groupby("candidate", dropna=False):
        role_totals = group.groupby("role")["total_pnl"].sum()
        role_trades = group.groupby("role")["trade_count"].sum()
        trade_count = int(group["trade_count"].sum())
        long_count = int(group["long_trade_count"].sum())
        short_count = int(group["short_trade_count"].sum())
        weights = group["trade_count"].astype(float)
        target_count = float((group["target_rate"] * weights).sum())
        row = {
            "candidate": candidate,
            "role_count": int(group["role"].nunique()),
            "month_count": int(group["month"].nunique()),
            "active_role_count": int((role_trades > 0).sum()),
            "positive_role_count": int((role_totals > 0).sum()),
            "active_months": int(group["trade_count"].gt(0).sum()),
            "total_pnl": float(group["total_pnl"].sum()),
            "min_role_total_pnl": float(role_totals.min()) if len(role_totals) else 0.0,
            "min_month_pnl": float(group["total_pnl"].min()) if len(group) else 0.0,
            "trade_count": trade_count,
            "min_role_trades": int(role_trades.min()) if len(role_trades) else 0,
            "min_month_trades": int(group["trade_count"].min()) if len(group) else 0,
            "max_drawdown": float(group["max_drawdown"].max()) if len(group) else 0.0,
            "long_trade_count": long_count,
            "short_trade_count": short_count,
            "max_side_trade_share": (
                float(max(long_count, short_count) / trade_count) if trade_count else 0.0
            ),
            "target_rate": float(target_count / trade_count) if trade_count else 0.0,
            "target_true_pnl": float(group["target_true_pnl"].sum()),
            "target_false_pnl": float(group["target_false_pnl"].sum()),
            "prediction_coverage": weighted_average(group["prediction_coverage"], weights),
            "predicted_risk_mean": weighted_average(group["predicted_risk_mean"], weights),
            "predicted_risk_p90_max": float(group["predicted_risk_p90"].max()),
            "high_risk_share": weighted_average(group["high_risk_share"], weights),
            "high_risk_share_predicted": weighted_average(
                group["high_risk_share_predicted"],
                weights,
            ),
            "high_risk_pnl": float(group["high_risk_pnl"].sum()),
            "no_prior_share": weighted_average(group["no_prior_share"], weights),
            "bucket_prediction_share": weighted_average(
                group["bucket_prediction_share"],
                weights,
            ),
            "global_prediction_share": weighted_average(
                group["global_prediction_share"],
                weights,
            ),
            "mean_prediction_support": weighted_average(
                group["mean_prediction_support"],
                weights,
            ),
        }
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [
            "min_role_total_pnl",
            "total_pnl",
            "predicted_risk_mean",
            "no_prior_share",
        ],
        ascending=[False, False, True, True],
    ).reset_index(drop=True)


def candidate_blockers(
    row: pd.Series,
    *,
    min_roles: int,
    min_positive_roles: int,
    min_active_roles: int,
    min_total_pnl: float,
    min_role_total_pnl: float,
    min_month_pnl: float,
    min_role_trades: int,
    min_month_trades: int,
    max_drawdown: float,
    max_side_trade_share: float,
    max_risk_mean: float,
    max_high_risk_share: float,
    max_no_prior_share: float,
    min_prediction_coverage: float,
) -> list[str]:
    risk_mean = float(row["predicted_risk_mean"])
    risk_mean_ok = bool(np.isfinite(risk_mean) and risk_mean <= max_risk_mean)
    if np.isinf(max_risk_mean):
        risk_mean_ok = True
    checks = [
        ("roles_low", row["role_count"] >= min_roles),
        ("positive_roles_low", row["positive_role_count"] >= min_positive_roles),
        ("active_roles_low", row["active_role_count"] >= min_active_roles),
        ("total_pnl_below_floor", row["total_pnl"] >= min_total_pnl),
        ("role_total_pnl_below_floor", row["min_role_total_pnl"] >= min_role_total_pnl),
        ("month_pnl_below_floor", row["min_month_pnl"] >= min_month_pnl),
        ("role_trades_low", row["min_role_trades"] >= min_role_trades),
        ("month_trades_low", row["min_month_trades"] >= min_month_trades),
        ("drawdown_high", row["max_drawdown"] <= max_drawdown),
        ("side_share_high", row["max_side_trade_share"] <= max_side_trade_share),
        ("predicted_ev_overestimate_risk_high", risk_mean_ok),
        ("high_risk_share_high", row["high_risk_share"] <= max_high_risk_share),
        ("no_prior_share_high", row["no_prior_share"] <= max_no_prior_share),
        ("prediction_coverage_low", row["prediction_coverage"] >= min_prediction_coverage),
    ]
    return [label for label, ok in checks if not bool(ok)]


def apply_selector_gates(
    summary: pd.DataFrame,
    *,
    min_roles: int,
    min_positive_roles: int,
    min_active_roles: int,
    min_total_pnl: float,
    min_role_total_pnl: float,
    min_month_pnl: float,
    min_role_trades: int,
    min_month_trades: int,
    max_drawdown: float,
    max_side_trade_share: float,
    max_risk_mean: float,
    max_high_risk_share: float,
    max_no_prior_share: float,
    min_prediction_coverage: float,
) -> pd.DataFrame:
    result = summary.copy()
    blockers: list[str] = []
    eligible: list[bool] = []
    for _, row in result.iterrows():
        row_blockers = candidate_blockers(
            row,
            min_roles=min_roles,
            min_positive_roles=min_positive_roles,
            min_active_roles=min_active_roles,
            min_total_pnl=min_total_pnl,
            min_role_total_pnl=min_role_total_pnl,
            min_month_pnl=min_month_pnl,
            min_role_trades=min_role_trades,
            min_month_trades=min_month_trades,
            max_drawdown=max_drawdown,
            max_side_trade_share=max_side_trade_share,
            max_risk_mean=max_risk_mean,
            max_high_risk_share=max_high_risk_share,
            max_no_prior_share=max_no_prior_share,
            min_prediction_coverage=min_prediction_coverage,
        )
        blockers.append(";".join(row_blockers))
        eligible.append(not row_blockers)
    result["eligible"] = eligible
    result["blockers"] = blockers
    return result.sort_values(
        [
            "eligible",
            "min_role_total_pnl",
            "total_pnl",
            "min_month_pnl",
            "predicted_risk_mean",
            "no_prior_share",
        ],
        ascending=[False, False, False, False, True, True],
    ).reset_index(drop=True)


def select_policy(gated: pd.DataFrame) -> dict[str, Any]:
    eligible = gated[gated["eligible"]]
    if eligible.empty:
        return {
            "selected": "no_trade",
            "reason": "no EV-overestimate risk candidate passed NoTrade-first gates",
        }
    row = eligible.iloc[0].to_dict()
    row["selected"] = "policy"
    row["reason"] = "best eligible candidate after EV-overestimate risk ranking"
    return row


def build_blocker_summary(gated: pd.DataFrame) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for blockers in gated["blockers"].fillna("").astype(str):
        for blocker in [part for part in blockers.split(";") if part]:
            counts[blocker] = counts.get(blocker, 0) + 1
    return pd.DataFrame(
        [{"blocker": blocker, "candidate_count": count} for blocker, count in counts.items()]
    ).sort_values(["candidate_count", "blocker"], ascending=[False, True])


def pointwise_screen_effects(
    frame: pd.DataFrame,
    *,
    target: str,
    thresholds: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for candidate, group in frame.groupby("candidate", dropna=False):
        base_role = group.groupby("role")["adjusted_pnl"].sum()
        base_month = group.groupby("month")["adjusted_pnl"].sum()
        base = {
            "candidate": candidate,
            "original_trades": int(len(group)),
            "original_total_pnl": float(group["adjusted_pnl"].sum()),
            "original_min_role_pnl": float(base_role.min()) if len(base_role) else 0.0,
            "original_min_month_pnl": float(base_month.min()) if len(base_month) else 0.0,
            "original_target_rate": float(group[target].astype(bool).mean()),
        }
        risk = group["predicted_ev_overestimate_risk"].astype(float)
        available = group["ev_overestimate_prediction_available"].astype(bool)
        no_prior = group["ev_overestimate_prediction_source"].astype(str).eq("no_prior")
        for threshold in thresholds:
            for mode, remove_mask in [
                ("predicted_high_only", available & risk.ge(threshold)),
                ("predicted_high_or_no_prior", (available & risk.ge(threshold)) | no_prior),
            ]:
                kept = group[~remove_mask]
                removed = group[remove_mask]
                kept_role = kept.groupby("role")["adjusted_pnl"].sum()
                kept_month = kept.groupby("month")["adjusted_pnl"].sum()
                row = dict(base)
                row.update(
                    {
                        "risk_threshold": threshold,
                        "screen_mode": mode,
                        "removed_trades": int(len(removed)),
                        "removed_pnl": float(removed["adjusted_pnl"].sum()) if len(removed) else 0.0,
                        "removed_target_rate": float(removed[target].astype(bool).mean())
                        if len(removed)
                        else 0.0,
                        "kept_trades": int(len(kept)),
                        "kept_total_pnl": float(kept["adjusted_pnl"].sum()) if len(kept) else 0.0,
                        "kept_min_role_pnl": float(kept_role.min()) if len(kept_role) else 0.0,
                        "kept_min_month_pnl": float(kept_month.min()) if len(kept_month) else 0.0,
                        "kept_target_rate": float(kept[target].astype(bool).mean())
                        if len(kept)
                        else 0.0,
                    }
                )
                rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["candidate", "risk_threshold", "screen_mode"],
    ).reset_index(drop=True)


def sensitivity_selection(
    summary: pd.DataFrame,
    *,
    args: argparse.Namespace,
    validation_role_count: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for max_risk_mean in parse_float_csv(args.max_risk_mean_grid):
        for max_high_share in parse_float_csv(args.max_high_risk_share_grid):
            for max_no_prior in parse_float_csv(args.max_no_prior_share_grid):
                for min_coverage in parse_float_csv(args.min_prediction_coverage_grid):
                    gated = apply_selector_gates(
                        summary,
                        min_roles=args.min_roles
                        if args.min_roles is not None
                        else validation_role_count,
                        min_positive_roles=args.min_positive_roles
                        if args.min_positive_roles is not None
                        else validation_role_count,
                        min_active_roles=args.min_active_roles
                        if args.min_active_roles is not None
                        else validation_role_count,
                        min_total_pnl=args.min_total_pnl,
                        min_role_total_pnl=args.min_role_total_pnl,
                        min_month_pnl=args.min_month_pnl,
                        min_role_trades=args.min_role_trades,
                        min_month_trades=args.min_month_trades,
                        max_drawdown=args.max_drawdown,
                        max_side_trade_share=args.max_side_trade_share,
                        max_risk_mean=max_risk_mean,
                        max_high_risk_share=max_high_share,
                        max_no_prior_share=max_no_prior,
                        min_prediction_coverage=min_coverage,
                    )
                    selected = select_policy(gated)
                    eligible = gated[gated["eligible"]]
                    rows.append(
                        {
                            "max_risk_mean": max_risk_mean,
                            "max_high_risk_share": max_high_share,
                            "max_no_prior_share": max_no_prior,
                            "min_prediction_coverage": min_coverage,
                            "eligible_count": int(len(eligible)),
                            "selected": selected.get("selected", "no_trade"),
                            "selected_candidate": selected.get("candidate", "no_trade"),
                            "selected_total_pnl": selected.get("total_pnl", 0.0),
                            "selected_min_role_total_pnl": selected.get(
                                "min_role_total_pnl",
                                0.0,
                            ),
                            "selected_min_month_pnl": selected.get("min_month_pnl", 0.0),
                            "selected_predicted_risk_mean": selected.get(
                                "predicted_risk_mean",
                                np.nan,
                            ),
                            "selected_no_prior_share": selected.get("no_prior_share", np.nan),
                            "reason": selected.get("reason", ""),
                        }
                    )
    return pd.DataFrame(rows)


def build_diagnostics(args: argparse.Namespace) -> Path:
    group_columns = parse_csv(args.group_columns)
    validation_roles = parse_csv(args.validation_roles)
    if not group_columns:
        raise ValueError("--group-columns must not be empty")
    if not validation_roles:
        raise ValueError("--validation-roles must not be empty")

    frame = read_component_frame(args.component_targets, target=args.target, group_columns=group_columns)
    risk_frame = build_chronological_ev_risk(
        frame,
        target=args.target,
        group_columns=group_columns,
        prior_strength=args.prior_strength,
        min_group_support=args.min_group_support,
    )
    validation = risk_frame[risk_frame["role"].isin(validation_roles)].copy()
    if validation.empty:
        raise ValueError("no rows matched --validation-roles")

    role_month = summarize_role_months(
        validation,
        target=args.target,
        risk_threshold=args.risk_threshold,
    )
    summary = summarize_candidates(role_month)
    validation_role_count = len(validation_roles)
    gated = apply_selector_gates(
        summary,
        min_roles=args.min_roles if args.min_roles is not None else validation_role_count,
        min_positive_roles=args.min_positive_roles
        if args.min_positive_roles is not None
        else validation_role_count,
        min_active_roles=args.min_active_roles
        if args.min_active_roles is not None
        else validation_role_count,
        min_total_pnl=args.min_total_pnl,
        min_role_total_pnl=args.min_role_total_pnl,
        min_month_pnl=args.min_month_pnl,
        min_role_trades=args.min_role_trades,
        min_month_trades=args.min_month_trades,
        max_drawdown=args.max_drawdown,
        max_side_trade_share=args.max_side_trade_share,
        max_risk_mean=args.max_risk_mean,
        max_high_risk_share=args.max_high_risk_share,
        max_no_prior_share=args.max_no_prior_share,
        min_prediction_coverage=args.min_prediction_coverage,
    )
    selection = select_policy(gated)
    blocker_summary = build_blocker_summary(gated)
    pointwise = pointwise_screen_effects(
        validation,
        target=args.target,
        thresholds=parse_float_csv(args.pointwise_thresholds),
    )
    sensitivity = sensitivity_selection(
        summary,
        args=args,
        validation_role_count=validation_role_count,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    risk_frame.to_csv(run_dir / "ev_overestimate_risk_trades.csv", index=False)
    role_month.to_csv(run_dir / "role_month_ev_overestimate_risk.csv", index=False)
    summary.to_csv(run_dir / "candidate_ev_overestimate_risk_summary.csv", index=False)
    gated.to_csv(run_dir / "candidate_ev_overestimate_risk_selection.csv", index=False)
    blocker_summary.to_csv(run_dir / "blocker_summary.csv", index=False)
    pointwise.to_csv(run_dir / "pointwise_risk_screen_effects.csv", index=False)
    sensitivity.to_csv(run_dir / "risk_selector_sensitivity.csv", index=False)
    (run_dir / "selected_policy.json").write_text(
        json.dumps(selection, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    config = {
        "component_targets": args.component_targets,
        "target": args.target,
        "group_columns": group_columns,
        "validation_roles": validation_roles,
        "prior_strength": args.prior_strength,
        "min_group_support": args.min_group_support,
        "risk_threshold": args.risk_threshold,
        "min_roles": args.min_roles,
        "min_positive_roles": args.min_positive_roles,
        "min_active_roles": args.min_active_roles,
        "min_total_pnl": args.min_total_pnl,
        "min_role_total_pnl": args.min_role_total_pnl,
        "min_month_pnl": args.min_month_pnl,
        "min_role_trades": args.min_role_trades,
        "min_month_trades": args.min_month_trades,
        "max_drawdown": args.max_drawdown,
        "max_side_trade_share": args.max_side_trade_share,
        "max_risk_mean": args.max_risk_mean,
        "max_high_risk_share": args.max_high_risk_share,
        "max_no_prior_share": args.max_no_prior_share,
        "min_prediction_coverage": args.min_prediction_coverage,
        "max_risk_mean_grid": args.max_risk_mean_grid,
        "max_high_risk_share_grid": args.max_high_risk_share_grid,
        "max_no_prior_share_grid": args.max_no_prior_share_grid,
        "min_prediction_coverage_grid": args.min_prediction_coverage_grid,
        "selection_uses_future_or_fixed_roles": False,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("EV-overestimate risk candidate selection:")
    print(
        gated[
            [
                "candidate",
                "eligible",
                "blockers",
                "total_pnl",
                "min_role_total_pnl",
                "min_month_pnl",
                "trade_count",
                "target_rate",
                "predicted_risk_mean",
                "high_risk_share",
                "prediction_coverage",
                "no_prior_share",
            ]
        ].to_string(index=False)
    )
    print("\nSensitivity selected counts:")
    print(sensitivity["selected_candidate"].value_counts(dropna=False).to_string())
    print(f"selected: {selection['selected']} ({selection['reason']})")
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-targets", type=Path, required=True)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--group-columns", default="support_bucket,pressure_bucket")
    parser.add_argument("--validation-roles", required=True)
    parser.add_argument("--prior-strength", type=float, default=5.0)
    parser.add_argument("--min-group-support", type=int, default=3)
    parser.add_argument("--risk-threshold", type=float, default=0.50)
    parser.add_argument("--min-roles", type=int, default=None)
    parser.add_argument("--min-positive-roles", type=int, default=None)
    parser.add_argument("--min-active-roles", type=int, default=None)
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-month-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-trades", type=int, default=1)
    parser.add_argument("--min-month-trades", type=int, default=1)
    parser.add_argument("--max-drawdown", type=float, default=float("inf"))
    parser.add_argument("--max-side-trade-share", type=float, default=float("inf"))
    parser.add_argument("--max-risk-mean", type=float, default=float("inf"))
    parser.add_argument("--max-high-risk-share", type=float, default=float("inf"))
    parser.add_argument("--max-no-prior-share", type=float, default=float("inf"))
    parser.add_argument("--min-prediction-coverage", type=float, default=0.0)
    parser.add_argument("--max-risk-mean-grid", default="inf,0.65,0.60,0.55,0.50,0.45")
    parser.add_argument("--max-high-risk-share-grid", default="inf,0.75,0.60,0.45,0.30")
    parser.add_argument("--max-no-prior-share-grid", default="inf,0.75,0.50,0.25")
    parser.add_argument("--min-prediction-coverage-grid", default="0,0.25,0.50,0.75")
    parser.add_argument("--pointwise-thresholds", default="0.45,0.50,0.55,0.60,0.65")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_overestimate_risk_selector")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
