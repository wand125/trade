#!/usr/bin/env python3
"""Select quantile admission policies from validation roles only."""

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


CANDIDATE_METADATA_COLUMNS = [
    "candidate",
    "scope",
    "score_quantile",
    "side_gap_quantile",
    "rank_quantile",
    "entry_threshold",
    "short_entry_threshold_offset",
    "side_margin",
    "min_entry_rank",
]


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


def read_monthly_metrics(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {
        "role",
        "month",
        "candidate",
        "total_adjusted_pnl",
        "trade_count",
        "max_drawdown",
        "long_trade_count",
        "short_trade_count",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
    return frame


def summarize_role_group(group: pd.DataFrame, prefix: str) -> dict[str, Any]:
    trades = group["trade_count"].astype(float)
    long_trades = float(group["long_trade_count"].astype(float).sum())
    short_trades = float(group["short_trade_count"].astype(float).sum())
    total_trades = float(trades.sum())
    return {
        f"{prefix}_role_count": int(group["role"].nunique()),
        f"{prefix}_month_count": int(group["month"].nunique()),
        f"{prefix}_active_role_count": int((group.groupby("role")["trade_count"].sum() > 0).sum()),
        f"{prefix}_positive_role_count": int(
            (group.groupby("role")["total_adjusted_pnl"].sum() > 0).sum()
        ),
        f"{prefix}_active_months": int((trades > 0).sum()),
        f"{prefix}_total_pnl": float(group["total_adjusted_pnl"].astype(float).sum()),
        f"{prefix}_min_role_total_pnl": float(
            group.groupby("role")["total_adjusted_pnl"].sum().min()
        ),
        f"{prefix}_min_month_pnl": float(group["total_adjusted_pnl"].astype(float).min()),
        f"{prefix}_trade_count": int(total_trades),
        f"{prefix}_min_role_trades": int(group.groupby("role")["trade_count"].sum().min()),
        f"{prefix}_min_month_trades": int(trades.min()),
        f"{prefix}_max_drawdown": float(group["max_drawdown"].astype(float).max()),
        f"{prefix}_long_trade_count": int(long_trades),
        f"{prefix}_short_trade_count": int(short_trades),
        f"{prefix}_max_side_trade_share": (
            float(max(long_trades, short_trades) / total_trades)
            if total_trades > 0
            else 0.0
        ),
    }


def summarize_candidates(
    monthly: pd.DataFrame,
    *,
    validation_roles: list[str],
    fixed_diagnostic_roles: list[str],
) -> pd.DataFrame:
    if not validation_roles:
        raise ValueError("at least one validation role is required")
    validation = monthly[monthly["role"].isin(validation_roles)].copy()
    if validation.empty:
        raise ValueError("no rows matched validation roles")
    fixed = monthly[monthly["role"].isin(fixed_diagnostic_roles)].copy()

    rows: list[dict[str, Any]] = []
    metadata_columns = [column for column in CANDIDATE_METADATA_COLUMNS if column in monthly.columns]
    for candidate, validation_group in validation.groupby("candidate", dropna=False):
        row: dict[str, Any] = {"candidate": candidate}
        for column in metadata_columns:
            if column == "candidate":
                continue
            row[column] = validation_group[column].iloc[0]
        row.update(summarize_role_group(validation_group, "validation"))
        fixed_group = fixed[fixed["candidate"] == candidate]
        if fixed_group.empty:
            row.update(
                {
                    "fixed_role_count": 0,
                    "fixed_month_count": 0,
                    "fixed_active_role_count": 0,
                    "fixed_positive_role_count": 0,
                    "fixed_active_months": 0,
                    "fixed_total_pnl": np.nan,
                    "fixed_min_role_total_pnl": np.nan,
                    "fixed_min_month_pnl": np.nan,
                    "fixed_trade_count": 0,
                    "fixed_min_role_trades": 0,
                    "fixed_min_month_trades": 0,
                    "fixed_max_drawdown": np.nan,
                    "fixed_long_trade_count": 0,
                    "fixed_short_trade_count": 0,
                    "fixed_max_side_trade_share": 0.0,
                }
            )
        else:
            row.update(summarize_role_group(fixed_group, "fixed"))
        rows.append(row)

    summary = pd.DataFrame(rows)
    return summary.sort_values(
        ["validation_min_role_total_pnl", "validation_total_pnl", "validation_min_month_pnl"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def candidate_blockers(
    row: pd.Series,
    *,
    min_validation_roles: int,
    min_positive_roles: int,
    min_active_roles: int,
    min_total_pnl: float,
    min_role_total_pnl: float,
    min_month_pnl: float,
    min_role_trades: int,
    min_month_trades: int,
    max_drawdown: float,
    max_side_trade_share: float,
) -> list[str]:
    blockers: list[str] = []
    checks = [
        ("validation_roles_low", row["validation_role_count"] >= min_validation_roles),
        ("positive_roles_low", row["validation_positive_role_count"] >= min_positive_roles),
        ("active_roles_low", row["validation_active_role_count"] >= min_active_roles),
        ("total_pnl_below_floor", row["validation_total_pnl"] >= min_total_pnl),
        (
            "role_total_pnl_below_floor",
            row["validation_min_role_total_pnl"] >= min_role_total_pnl,
        ),
        ("month_pnl_below_floor", row["validation_min_month_pnl"] >= min_month_pnl),
        ("role_trades_low", row["validation_min_role_trades"] >= min_role_trades),
        ("month_trades_low", row["validation_min_month_trades"] >= min_month_trades),
        ("drawdown_high", row["validation_max_drawdown"] <= max_drawdown),
        (
            "side_share_high",
            row["validation_max_side_trade_share"] <= max_side_trade_share,
        ),
    ]
    for label, ok in checks:
        if not bool(ok):
            blockers.append(label)
    return blockers


def apply_selector_gates(
    summary: pd.DataFrame,
    *,
    min_validation_roles: int,
    min_positive_roles: int,
    min_active_roles: int,
    min_total_pnl: float,
    min_role_total_pnl: float,
    min_month_pnl: float,
    min_role_trades: int,
    min_month_trades: int,
    max_drawdown: float,
    max_side_trade_share: float,
) -> pd.DataFrame:
    result = summary.copy()
    blocker_values: list[str] = []
    eligible_values: list[bool] = []
    for _, row in result.iterrows():
        blockers = candidate_blockers(
            row,
            min_validation_roles=min_validation_roles,
            min_positive_roles=min_positive_roles,
            min_active_roles=min_active_roles,
            min_total_pnl=min_total_pnl,
            min_role_total_pnl=min_role_total_pnl,
            min_month_pnl=min_month_pnl,
            min_role_trades=min_role_trades,
            min_month_trades=min_month_trades,
            max_drawdown=max_drawdown,
            max_side_trade_share=max_side_trade_share,
        )
        blocker_values.append(";".join(blockers))
        eligible_values.append(not blockers)
    result["eligible"] = eligible_values
    result["blockers"] = blocker_values
    return result.sort_values(
        [
            "eligible",
            "validation_min_role_total_pnl",
            "validation_total_pnl",
            "validation_min_month_pnl",
            "validation_max_drawdown",
        ],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)


def select_policy(gated: pd.DataFrame) -> dict[str, Any]:
    eligible = gated[gated["eligible"]]
    if eligible.empty:
        return {
            "selected": "no_trade",
            "reason": "no validation-role candidate passed the pre-registered gates",
        }
    selected = eligible.iloc[0].to_dict()
    selected["selected"] = "policy"
    selected["reason"] = "best eligible validation-role candidate"
    return selected


def build_blocker_summary(gated: pd.DataFrame) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for blockers in gated["blockers"].fillna("").astype(str):
        for blocker in [part for part in blockers.split(";") if part]:
            counts[blocker] = counts.get(blocker, 0) + 1
    return pd.DataFrame(
        [{"blocker": blocker, "candidate_count": count} for blocker, count in counts.items()]
    ).sort_values(["candidate_count", "blocker"], ascending=[False, True])


def run_selection(args: argparse.Namespace) -> Path:
    validation_roles = parse_csv(args.validation_roles)
    fixed_diagnostic_roles = parse_csv(args.fixed_diagnostic_roles)
    min_validation_roles = (
        args.min_validation_roles
        if args.min_validation_roles is not None
        else len(validation_roles)
    )
    min_positive_roles = (
        args.min_positive_roles
        if args.min_positive_roles is not None
        else len(validation_roles)
    )
    min_active_roles = (
        args.min_active_roles
        if args.min_active_roles is not None
        else len(validation_roles)
    )

    monthly = read_monthly_metrics(args.monthly_metrics)
    summary = summarize_candidates(
        monthly,
        validation_roles=validation_roles,
        fixed_diagnostic_roles=fixed_diagnostic_roles,
    )
    gated = apply_selector_gates(
        summary,
        min_validation_roles=min_validation_roles,
        min_positive_roles=min_positive_roles,
        min_active_roles=min_active_roles,
        min_total_pnl=args.min_total_pnl,
        min_role_total_pnl=args.min_role_total_pnl,
        min_month_pnl=args.min_month_pnl,
        min_role_trades=args.min_role_trades,
        min_month_trades=args.min_month_trades,
        max_drawdown=args.max_drawdown,
        max_side_trade_share=args.max_side_trade_share,
    )
    selected = select_policy(gated)
    blocker_summary = build_blocker_summary(gated)

    run_dir = make_run_dir(args.output_dir, args.label)
    gated.to_csv(run_dir / "candidate_selection_summary.csv", index=False)
    blocker_summary.to_csv(run_dir / "blocker_summary.csv", index=False)
    (run_dir / "selected_policy.json").write_text(
        json.dumps(selected, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    config = {
        "monthly_metrics": args.monthly_metrics,
        "validation_roles": validation_roles,
        "fixed_diagnostic_roles": fixed_diagnostic_roles,
        "min_validation_roles": min_validation_roles,
        "min_positive_roles": min_positive_roles,
        "min_active_roles": min_active_roles,
        "min_total_pnl": args.min_total_pnl,
        "min_role_total_pnl": args.min_role_total_pnl,
        "min_month_pnl": args.min_month_pnl,
        "min_role_trades": args.min_role_trades,
        "min_month_trades": args.min_month_trades,
        "max_drawdown": args.max_drawdown,
        "max_side_trade_share": args.max_side_trade_share,
        "selection_uses_fixed_diagnostic_roles": False,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print(
        gated[
            [
                "candidate",
                "eligible",
                "blockers",
                "validation_total_pnl",
                "validation_min_role_total_pnl",
                "validation_min_month_pnl",
                "validation_trade_count",
                "validation_max_drawdown",
                "validation_max_side_trade_share",
                "fixed_total_pnl",
                "fixed_min_month_pnl",
            ]
        ].to_string(index=False)
    )
    print(f"selected: {selected['selected']} ({selected['reason']})")
    if selected["selected"] == "policy":
        print(f"candidate: {selected['candidate']}")
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monthly-metrics", type=Path, required=True)
    parser.add_argument("--validation-roles", required=True)
    parser.add_argument("--fixed-diagnostic-roles", default="")
    parser.add_argument("--min-validation-roles", type=int, default=None)
    parser.add_argument("--min-positive-roles", type=int, default=None)
    parser.add_argument("--min-active-roles", type=int, default=None)
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-month-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-trades", type=int, default=10)
    parser.add_argument("--min-month-trades", type=int, default=1)
    parser.add_argument("--max-drawdown", type=float, default=float("inf"))
    parser.add_argument("--max-side-trade-share", type=float, default=0.95)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_quantile_policy_selection")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_selection(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
