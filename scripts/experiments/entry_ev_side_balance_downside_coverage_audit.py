#!/usr/bin/env python3
"""Audit coverage/support constraints for side-balance downside features."""

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
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


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


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def read_role_month(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {
        "candidate",
        "role",
        "month",
        "trade_count",
        "total_pnl",
        "prior_zero_share",
        "prior_support_mean",
        "feature_pressure_score",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["candidate"] = output["candidate"].astype(str)
    output["role"] = output["role"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    for column in [
        "trade_count",
        "total_pnl",
        "max_drawdown",
        "risk_high_share",
        "interaction_high_share",
        "prior_zero_share",
        "prior_support_mean",
        "feature_pressure_score",
        "uncovered_loss_pnl",
    ]:
        output[column] = numeric_series(output, column)
    return output


def weighted_average(values: pd.Series, weights: pd.Series) -> float:
    values = values.astype(float)
    weights = weights.astype(float)
    total_weight = float(weights.sum())
    if total_weight <= 0.0:
        return 0.0
    return float(np.average(values, weights=weights))


def summarize_role(
    frame: pd.DataFrame,
    *,
    candidate: str,
    role: str,
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
            "role_max_drawdown": 0.0,
            "role_prior_zero_share": 1.0,
            "role_prior_support_mean": 0.0,
            "role_feature_pressure_score": 1.0,
            "role_max_month_feature_pressure_score": 1.0,
            "role_uncovered_loss_pnl": 0.0,
        }
    weights = frame["trade_count"].astype(float)
    return {
        "candidate": candidate,
        "role": role,
        "role_present": True,
        "role_active": bool(weights.sum() > 0),
        "role_trade_count": int(weights.sum()),
        "role_month_count": int(frame["month"].nunique()),
        "role_active_month_count": int(frame["trade_count"].astype(float).gt(0).sum()),
        "role_total_pnl": float(frame["total_pnl"].astype(float).sum()),
        "role_min_month_pnl": float(frame["total_pnl"].astype(float).min()),
        "role_max_drawdown": float(frame["max_drawdown"].astype(float).max()),
        "role_prior_zero_share": weighted_average(frame["prior_zero_share"], weights),
        "role_prior_support_mean": weighted_average(frame["prior_support_mean"], weights),
        "role_feature_pressure_score": weighted_average(
            frame["feature_pressure_score"],
            weights,
        ),
        "role_max_month_feature_pressure_score": float(
            frame["feature_pressure_score"].astype(float).max()
        ),
        "role_uncovered_loss_pnl": float(frame["uncovered_loss_pnl"].astype(float).sum()),
    }


def summarize_coverage(frame: pd.DataFrame, required_roles: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    role_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for candidate, candidate_frame in frame.groupby("candidate", dropna=False):
        candidate_role_rows: list[dict[str, Any]] = []
        for role in required_roles:
            role_frame = candidate_frame[candidate_frame["role"].eq(role)]
            role_row = summarize_role(role_frame, candidate=candidate, role=role)
            candidate_role_rows.append(role_row)
            role_rows.append(role_row)
        role_summary = pd.DataFrame(candidate_role_rows)
        active_roles = role_summary[role_summary["role_active"]]
        missing_roles = role_summary[~role_summary["role_present"]]["role"].astype(str).tolist()
        inactive_roles = role_summary[~role_summary["role_active"]]["role"].astype(str).tolist()
        role_trade_count = role_summary["role_trade_count"].astype(float)
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
                "trade_count": int(role_trade_count.sum()),
                "min_required_role_trades": int(role_trade_count.min()),
                "min_active_role_trades": (
                    int(active_roles["role_trade_count"].min()) if not active_roles.empty else 0
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
                "max_required_month_feature_pressure_score": float(
                    role_summary["role_max_month_feature_pressure_score"].max()
                ),
                "uncovered_loss_pnl": float(role_summary["role_uncovered_loss_pnl"].sum()),
            }
        )
    return (
        pd.DataFrame(candidate_rows).sort_values(
            [
                "active_required_role_count",
                "min_required_role_total_pnl",
                "total_pnl",
                "max_required_role_prior_zero_share",
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
    max_required_role_prior_zero_share: float,
    min_required_role_prior_support_mean: float,
    max_required_role_feature_pressure_score: float,
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
        (
            "required_role_prior_zero_high",
            row["max_required_role_prior_zero_share"] <= max_required_role_prior_zero_share,
        ),
        (
            "required_role_prior_support_low",
            row["min_required_role_prior_support_mean"] >= min_required_role_prior_support_mean,
        ),
        (
            "required_role_pressure_high",
            row["max_required_role_feature_pressure_score"]
            <= max_required_role_feature_pressure_score,
        ),
    ]
    return [label for label, ok in checks if not bool(ok)]


def apply_coverage_gates(
    summary: pd.DataFrame,
    *,
    required_role_count: int,
    min_active_required_roles: int,
    min_required_role_trades: int,
    min_total_pnl: float,
    min_required_role_total_pnl: float,
    min_required_month_pnl: float,
    max_required_role_prior_zero_share: float,
    min_required_role_prior_support_mean: float,
    max_required_role_feature_pressure_score: float,
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
            max_required_role_prior_zero_share=max_required_role_prior_zero_share,
            min_required_role_prior_support_mean=min_required_role_prior_support_mean,
            max_required_role_feature_pressure_score=max_required_role_feature_pressure_score,
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
            "max_required_role_feature_pressure_score",
            "max_required_role_prior_zero_share",
        ],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)


def select_policy(gated: pd.DataFrame) -> dict[str, Any]:
    eligible = gated[gated["eligible"]]
    if eligible.empty:
        return {
            "selected": "no_trade",
            "reason": "no candidate passed coverage/support gates",
        }
    selected = eligible.iloc[0].to_dict()
    selected["selected"] = "policy"
    selected["reason"] = "best eligible candidate after coverage/support audit"
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
                        gated = apply_coverage_gates(
                            summary,
                            required_role_count=required_role_count,
                            min_active_required_roles=active_roles,
                            min_required_role_trades=role_trades,
                            min_total_pnl=args.min_total_pnl,
                            min_required_role_total_pnl=args.min_required_role_total_pnl,
                            min_required_month_pnl=args.min_required_month_pnl,
                            max_required_role_prior_zero_share=prior_zero,
                            min_required_role_prior_support_mean=support,
                            max_required_role_feature_pressure_score=pressure,
                        )
                        selection = select_policy(gated)
                        row = {
                            "min_active_required_roles": active_roles,
                            "min_required_role_trades": role_trades,
                            "max_required_role_prior_zero_share": prior_zero,
                            "min_required_role_prior_support_mean": support,
                            "max_required_role_feature_pressure_score": pressure,
                            "eligible_candidate_count": int(gated["eligible"].sum()),
                            "selected": selection["selected"],
                            "reason": selection["reason"],
                            "candidate": "",
                            "total_pnl": np.nan,
                            "min_required_role_total_pnl": np.nan,
                            "min_required_month_pnl": np.nan,
                            "trade_count": 0,
                            "active_required_role_count": 0,
                            "max_required_role_prior_zero_share_value": np.nan,
                            "max_required_role_feature_pressure_score_value": np.nan,
                        }
                        if selection["selected"] == "policy":
                            for column in [
                                "candidate",
                                "total_pnl",
                                "min_required_role_total_pnl",
                                "min_required_month_pnl",
                                "trade_count",
                                "active_required_role_count",
                                "max_required_role_prior_zero_share",
                                "max_required_role_feature_pressure_score",
                            ]:
                                output_column = column
                                if column.startswith("max_required_role_"):
                                    output_column = f"{column}_value"
                                row[output_column] = selection.get(column)
                        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        [
            "selected",
            "min_required_role_total_pnl",
            "total_pnl",
            "eligible_candidate_count",
        ],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def build_audit(args: argparse.Namespace) -> Path:
    required_roles = parse_csv(args.required_roles)
    if not required_roles:
        raise ValueError("--required-roles must not be empty")
    frame = read_role_month(args.role_month_features)
    candidate_summary, role_summary = summarize_coverage(frame, required_roles)
    gated = apply_coverage_gates(
        candidate_summary,
        required_role_count=len(required_roles),
        min_active_required_roles=args.min_active_required_roles,
        min_required_role_trades=args.min_required_role_trades,
        min_total_pnl=args.min_total_pnl,
        min_required_role_total_pnl=args.min_required_role_total_pnl,
        min_required_month_pnl=args.min_required_month_pnl,
        max_required_role_prior_zero_share=args.max_required_role_prior_zero_share,
        min_required_role_prior_support_mean=args.min_required_role_prior_support_mean,
        max_required_role_feature_pressure_score=args.max_required_role_feature_pressure_score,
    )
    selection = select_policy(gated)
    blocker_summary = build_blocker_summary(gated)
    sensitivity = summarize_gate_sensitivity(
        candidate_summary,
        args,
        required_role_count=len(required_roles),
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    candidate_summary.to_csv(run_dir / "coverage_candidate_summary.csv", index=False)
    role_summary.to_csv(run_dir / "coverage_role_summary.csv", index=False)
    gated.to_csv(run_dir / "coverage_candidate_selection.csv", index=False)
    blocker_summary.to_csv(run_dir / "blocker_summary.csv", index=False)
    sensitivity.to_csv(run_dir / "coverage_gate_sensitivity.csv", index=False)
    (run_dir / "selected_policy.json").write_text(
        json.dumps(selection, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    config = {
        "role_month_features": args.role_month_features,
        "required_roles": required_roles,
        "min_active_required_roles": args.min_active_required_roles,
        "min_required_role_trades": args.min_required_role_trades,
        "min_total_pnl": args.min_total_pnl,
        "min_required_role_total_pnl": args.min_required_role_total_pnl,
        "min_required_month_pnl": args.min_required_month_pnl,
        "max_required_role_prior_zero_share": args.max_required_role_prior_zero_share,
        "min_required_role_prior_support_mean": args.min_required_role_prior_support_mean,
        "max_required_role_feature_pressure_score": args.max_required_role_feature_pressure_score,
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
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Coverage candidate selection:")
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
                "min_required_role_prior_support_mean",
                "max_required_role_feature_pressure_score",
                "uncovered_loss_pnl",
            ]
        ].to_string(index=False)
    )
    print(f"selected: {selection['selected']} ({selection['reason']})")
    print("\nCoverage gate sensitivity:")
    print(sensitivity.head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-month-features", type=Path, required=True)
    parser.add_argument("--required-roles", required=True)
    parser.add_argument("--min-active-required-roles", type=int, default=3)
    parser.add_argument("--min-required-role-trades", type=int, default=1)
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-required-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-required-month-pnl", type=float, default=0.0)
    parser.add_argument("--max-required-role-prior-zero-share", type=float, default=0.75)
    parser.add_argument("--min-required-role-prior-support-mean", type=float, default=0.0)
    parser.add_argument(
        "--max-required-role-feature-pressure-score",
        type=float,
        default=0.50,
    )
    parser.add_argument("--min-active-required-roles-grid", default="3,2")
    parser.add_argument("--min-required-role-trades-grid", default="1,5,10")
    parser.add_argument("--max-required-role-prior-zero-share-grid", default="0.50,0.75,0.95,inf")
    parser.add_argument("--min-required-role-prior-support-mean-grid", default="0.00,0.10,0.25")
    parser.add_argument("--max-required-role-feature-pressure-score-grid", default="0.35,0.50,inf")
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_side_balance_downside_coverage_audit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_audit(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
