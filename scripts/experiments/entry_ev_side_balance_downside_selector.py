#!/usr/bin/env python3
"""Evaluate side-balance/downside features in candidate-level selection."""

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


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def read_trade_frames(paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in paths]
    if not frames:
        raise ValueError("at least one enriched side-balance downside trade CSV is required")
    return pd.concat(frames, ignore_index=True)


def filter_values(frame: pd.DataFrame, column: str, values: list[str]) -> pd.DataFrame:
    if not values:
        return frame.copy()
    return frame[frame[column].astype(str).isin(values)].copy()


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


def summarize_trade_slice(
    frame: pd.DataFrame,
    *,
    risk_threshold: float,
    interaction_threshold: float,
) -> dict[str, Any]:
    if frame.empty:
        return {
            "trade_count": 0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "long_trade_count": 0,
            "short_trade_count": 0,
            "max_side_trade_share": 0.0,
            "risk_mean": 0.0,
            "risk_p75": 0.0,
            "risk_p90": 0.0,
            "risk_high_share": 0.0,
            "interaction_mean": 0.0,
            "interaction_p75": 0.0,
            "interaction_p90": 0.0,
            "interaction_high_share": 0.0,
            "abs_drift_mean": 0.0,
            "signed_drift_mean": 0.0,
            "prior_zero_share": 0.0,
            "prior_support_mean": 0.0,
            "overrepresented_share": 0.0,
            "underrepresented_share": 0.0,
            "feature_pressure_score": 0.0,
            "uncovered_loss_pnl": 0.0,
            "uncovered_loss_count": 0,
        }
    ordered = frame.sort_values("entry_decision_timestamp")
    pnl = ordered["adjusted_pnl"].astype(float)
    direction = ordered["direction"].astype(str).str.lower()
    risk = ordered["prior_downside_risk_score"].astype(float)
    interaction = ordered["side_balance_downside_interaction_score"].astype(float)
    abs_drift = ordered["side_balance_abs_signed_drift_for_trade"].astype(float)
    signed_drift = ordered["side_balance_signed_drift_for_trade"].astype(float)
    prior_trade_count = ordered["prior_trade_count"].astype(float)
    support = ordered["prior_downside_support_weight"].astype(float)
    risk_high = risk >= risk_threshold
    interaction_high = interaction >= interaction_threshold
    prior_zero = prior_trade_count <= 0.0
    uncovered_loss = pnl.lt(0.0) & (prior_zero | ~risk_high | ~interaction_high)
    trade_count = int(len(ordered))
    long_count = int(direction.eq("long").sum())
    short_count = int(direction.eq("short").sum())
    risk_high_share = float(risk_high.mean())
    interaction_high_share = float(interaction_high.mean())
    risk_mean = float(risk.mean())
    prior_zero_share = float(prior_zero.mean())
    return {
        "trade_count": trade_count,
        "total_pnl": float(pnl.sum()),
        "avg_pnl": float(pnl.mean()),
        "win_rate": float(pnl.gt(0.0).mean()),
        "max_drawdown": cumulative_max_drawdown(pnl),
        "long_trade_count": long_count,
        "short_trade_count": short_count,
        "max_side_trade_share": float(max(long_count, short_count) / trade_count),
        "risk_mean": risk_mean,
        "risk_p75": float(risk.quantile(0.75)),
        "risk_p90": float(risk.quantile(0.90)),
        "risk_high_share": risk_high_share,
        "interaction_mean": float(interaction.mean()),
        "interaction_p75": float(interaction.quantile(0.75)),
        "interaction_p90": float(interaction.quantile(0.90)),
        "interaction_high_share": interaction_high_share,
        "abs_drift_mean": float(abs_drift.mean()),
        "signed_drift_mean": float(signed_drift.mean()),
        "prior_zero_share": prior_zero_share,
        "prior_support_mean": float(support.mean()),
        "overrepresented_share": float(
            ordered["side_balance_selected_side_overrepresented"].astype(bool).mean()
        ),
        "underrepresented_share": float(
            ordered["side_balance_selected_side_underrepresented"].astype(bool).mean()
        ),
        "feature_pressure_score": feature_pressure_score(
            risk_high_share=risk_high_share,
            interaction_high_share=interaction_high_share,
            risk_mean=risk_mean,
            prior_zero_share=prior_zero_share,
        ),
        "uncovered_loss_pnl": float(pnl.where(uncovered_loss, 0.0).sum()),
        "uncovered_loss_count": int(uncovered_loss.sum()),
    }


def summarize_role_months(
    frame: pd.DataFrame,
    *,
    risk_threshold: float,
    interaction_threshold: float,
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
                risk_threshold=risk_threshold,
                interaction_threshold=interaction_threshold,
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
            "risk_mean": weighted_average(group["risk_mean"], weights),
            "risk_p90_max": float(group["risk_p90"].max()),
            "risk_high_share": weighted_average(group["risk_high_share"], weights),
            "max_role_month_risk_high_share": float(group["risk_high_share"].max()),
            "interaction_mean": weighted_average(group["interaction_mean"], weights),
            "interaction_p90_max": float(group["interaction_p90"].max()),
            "interaction_high_share": weighted_average(
                group["interaction_high_share"],
                weights,
            ),
            "max_role_month_interaction_high_share": float(
                group["interaction_high_share"].max()
            ),
            "abs_drift_mean": weighted_average(group["abs_drift_mean"], weights),
            "prior_zero_share": weighted_average(group["prior_zero_share"], weights),
            "max_role_month_prior_zero_share": float(group["prior_zero_share"].max()),
            "prior_support_mean": weighted_average(group["prior_support_mean"], weights),
            "feature_pressure_score": weighted_average(
                group["feature_pressure_score"],
                weights,
            ),
            "max_role_month_feature_pressure_score": float(
                group["feature_pressure_score"].max()
            ),
            "uncovered_loss_pnl": float(group["uncovered_loss_pnl"].sum()),
            "uncovered_loss_count": int(group["uncovered_loss_count"].sum()),
        }
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [
            "min_role_total_pnl",
            "total_pnl",
            "min_month_pnl",
            "feature_pressure_score",
        ],
        ascending=[False, False, False, True],
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
    max_risk_high_share: float,
    max_interaction_high_share: float,
    max_prior_zero_share: float,
    max_feature_pressure_score: float,
) -> list[str]:
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
        ("risk_high_share_high", row["risk_high_share"] <= max_risk_high_share),
        (
            "interaction_high_share_high",
            row["interaction_high_share"] <= max_interaction_high_share,
        ),
        ("prior_zero_share_high", row["prior_zero_share"] <= max_prior_zero_share),
        (
            "feature_pressure_high",
            row["feature_pressure_score"] <= max_feature_pressure_score,
        ),
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
    max_risk_high_share: float,
    max_interaction_high_share: float,
    max_prior_zero_share: float,
    max_feature_pressure_score: float,
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
            max_risk_high_share=max_risk_high_share,
            max_interaction_high_share=max_interaction_high_share,
            max_prior_zero_share=max_prior_zero_share,
            max_feature_pressure_score=max_feature_pressure_score,
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
            "feature_pressure_score",
            "max_drawdown",
        ],
        ascending=[False, False, False, False, True, True],
    ).reset_index(drop=True)


def select_policy(gated: pd.DataFrame) -> dict[str, Any]:
    eligible = gated[gated["eligible"]]
    if eligible.empty:
        return {
            "selected": "no_trade",
            "reason": "no side-balance/downside candidate passed selector gates",
        }
    selected = eligible.iloc[0].to_dict()
    selected["selected"] = "policy"
    selected["reason"] = "best eligible candidate after side-balance/downside ranking"
    return selected


def build_blocker_summary(gated: pd.DataFrame) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for blockers in gated["blockers"].fillna("").astype(str):
        for blocker in [part for part in blockers.split(";") if part]:
            counts[blocker] = counts.get(blocker, 0) + 1
    return pd.DataFrame(
        [{"blocker": blocker, "candidate_count": count} for blocker, count in counts.items()]
    ).sort_values(["candidate_count", "blocker"], ascending=[False, True])


def summarize_feature_gate_grid(
    summary: pd.DataFrame,
    args: argparse.Namespace,
    *,
    min_roles: int,
    min_positive_roles: int,
    min_active_roles: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for risk_share in parse_float_csv(args.max_risk_high_shares):
        for interaction_share in parse_float_csv(args.max_interaction_high_shares):
            for prior_zero_share in parse_float_csv(args.max_prior_zero_shares):
                for pressure in parse_float_csv(args.max_feature_pressure_scores):
                    gated = apply_selector_gates(
                        summary,
                        min_roles=min_roles,
                        min_positive_roles=min_positive_roles,
                        min_active_roles=min_active_roles,
                        min_total_pnl=args.min_total_pnl,
                        min_role_total_pnl=args.min_role_total_pnl,
                        min_month_pnl=args.min_month_pnl,
                        min_role_trades=args.min_role_trades,
                        min_month_trades=args.min_month_trades,
                        max_drawdown=args.max_drawdown,
                        max_side_trade_share=args.max_side_trade_share,
                        max_risk_high_share=risk_share,
                        max_interaction_high_share=interaction_share,
                        max_prior_zero_share=prior_zero_share,
                        max_feature_pressure_score=pressure,
                    )
                    selection = select_policy(gated)
                    row = {
                        "max_risk_high_share": risk_share,
                        "max_interaction_high_share": interaction_share,
                        "max_prior_zero_share": prior_zero_share,
                        "max_feature_pressure_score": pressure,
                        "eligible_candidate_count": int(gated["eligible"].sum()),
                        "selected": selection["selected"],
                        "reason": selection["reason"],
                        "candidate": "",
                        "total_pnl": np.nan,
                        "min_role_total_pnl": np.nan,
                        "min_month_pnl": np.nan,
                        "trade_count": 0,
                        "risk_high_share": np.nan,
                        "interaction_high_share": np.nan,
                        "prior_zero_share": np.nan,
                        "feature_pressure_score": np.nan,
                        "uncovered_loss_pnl": np.nan,
                    }
                    if selection["selected"] == "policy":
                        for column in [
                            "candidate",
                            "total_pnl",
                            "min_role_total_pnl",
                            "min_month_pnl",
                            "trade_count",
                            "risk_high_share",
                            "interaction_high_share",
                            "prior_zero_share",
                            "feature_pressure_score",
                            "uncovered_loss_pnl",
                        ]:
                            row[column] = selection.get(column)
                    rows.append(row)
    return pd.DataFrame(rows).sort_values(
        [
            "selected",
            "min_role_total_pnl",
            "total_pnl",
            "feature_pressure_score",
            "max_feature_pressure_score",
        ],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)


def build_diagnostics(args: argparse.Namespace) -> Path:
    trades = normalize_trades(read_trade_frames(args.trades))
    trades = filter_values(trades, "role", parse_csv(args.roles))
    trades = filter_values(trades, "candidate", parse_csv(args.candidates))
    if trades.empty:
        raise ValueError("no trades remain after filters")

    role_month = summarize_role_months(
        trades,
        risk_threshold=args.risk_threshold,
        interaction_threshold=args.interaction_threshold,
    )
    summary = summarize_candidates(role_month)
    min_roles = args.min_roles if args.min_roles is not None else len(parse_csv(args.roles))
    min_positive_roles = (
        args.min_positive_roles
        if args.min_positive_roles is not None
        else len(parse_csv(args.roles))
    )
    min_active_roles = (
        args.min_active_roles if args.min_active_roles is not None else len(parse_csv(args.roles))
    )
    gated = apply_selector_gates(
        summary,
        min_roles=min_roles,
        min_positive_roles=min_positive_roles,
        min_active_roles=min_active_roles,
        min_total_pnl=args.min_total_pnl,
        min_role_total_pnl=args.min_role_total_pnl,
        min_month_pnl=args.min_month_pnl,
        min_role_trades=args.min_role_trades,
        min_month_trades=args.min_month_trades,
        max_drawdown=args.max_drawdown,
        max_side_trade_share=args.max_side_trade_share,
        max_risk_high_share=args.max_risk_high_share,
        max_interaction_high_share=args.max_interaction_high_share,
        max_prior_zero_share=args.max_prior_zero_share,
        max_feature_pressure_score=args.max_feature_pressure_score,
    )
    selection = select_policy(gated)
    blocker_summary = build_blocker_summary(gated)
    grid = summarize_feature_gate_grid(
        summary,
        args,
        min_roles=min_roles,
        min_positive_roles=min_positive_roles,
        min_active_roles=min_active_roles,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    role_month.to_csv(run_dir / "role_month_side_balance_downside_features.csv", index=False)
    gated.to_csv(run_dir / "candidate_side_balance_downside_selection.csv", index=False)
    blocker_summary.to_csv(run_dir / "blocker_summary.csv", index=False)
    grid.to_csv(run_dir / "feature_gate_sensitivity.csv", index=False)
    (run_dir / "selected_policy.json").write_text(
        json.dumps(selection, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    config = {
        "trades": args.trades,
        "roles": parse_csv(args.roles),
        "candidates": parse_csv(args.candidates),
        "risk_threshold": args.risk_threshold,
        "interaction_threshold": args.interaction_threshold,
        "min_roles": min_roles,
        "min_positive_roles": min_positive_roles,
        "min_active_roles": min_active_roles,
        "min_total_pnl": args.min_total_pnl,
        "min_role_total_pnl": args.min_role_total_pnl,
        "min_month_pnl": args.min_month_pnl,
        "min_role_trades": args.min_role_trades,
        "min_month_trades": args.min_month_trades,
        "max_drawdown": args.max_drawdown,
        "max_side_trade_share": args.max_side_trade_share,
        "max_risk_high_share": args.max_risk_high_share,
        "max_interaction_high_share": args.max_interaction_high_share,
        "max_prior_zero_share": args.max_prior_zero_share,
        "max_feature_pressure_score": args.max_feature_pressure_score,
        "max_risk_high_shares": parse_float_csv(args.max_risk_high_shares),
        "max_interaction_high_shares": parse_float_csv(
            args.max_interaction_high_shares
        ),
        "max_prior_zero_shares": parse_float_csv(args.max_prior_zero_shares),
        "max_feature_pressure_scores": parse_float_csv(
            args.max_feature_pressure_scores
        ),
        "note": "selection uses validation roles only; feature gates are candidate-level diagnostics",
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Side-balance/downside candidate selection:")
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
                "risk_high_share",
                "interaction_high_share",
                "prior_zero_share",
                "feature_pressure_score",
                "uncovered_loss_pnl",
            ]
        ]
        .head(args.top_n)
        .to_string(index=False)
    )
    print(f"selected: {selection['selected']} ({selection['reason']})")
    print("\nFeature gate sensitivity:")
    print(grid.head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=Path, action="append", required=True)
    parser.add_argument("--roles", required=True)
    parser.add_argument("--candidates", default="")
    parser.add_argument("--risk-threshold", type=float, default=0.20)
    parser.add_argument("--interaction-threshold", type=float, default=0.005)
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
    parser.add_argument("--max-risk-high-share", type=float, default=float("inf"))
    parser.add_argument("--max-interaction-high-share", type=float, default=float("inf"))
    parser.add_argument("--max-prior-zero-share", type=float, default=float("inf"))
    parser.add_argument("--max-feature-pressure-score", type=float, default=float("inf"))
    parser.add_argument("--max-risk-high-shares", default="inf,0.75,0.50,0.25")
    parser.add_argument("--max-interaction-high-shares", default="inf,0.75,0.50,0.25")
    parser.add_argument("--max-prior-zero-shares", default="inf,0.75,0.50,0.25")
    parser.add_argument("--max-feature-pressure-scores", default="inf,0.50,0.35,0.20")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_side_balance_downside_selector")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
