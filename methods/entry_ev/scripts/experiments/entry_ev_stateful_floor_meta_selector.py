#!/usr/bin/env python3
"""Rank stateful policy candidates with explicit role/month floor penalties."""

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

from entry_ev_supervised_shrinkage_policy_inputs import local_json_default  # noqa: E402


REQUIRED_COLUMNS = {
    "role",
    "month",
    "candidate",
    "total_adjusted_pnl",
    "trade_count",
    "max_drawdown",
}


def parse_labeled_paths(values: list[str]) -> list[tuple[str, Path]]:
    pairs: list[tuple[str, Path]] = []
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("monthly metrics must use label=path")
        label, path_text = value.split("=", 1)
        label = label.strip()
        if not label:
            raise argparse.ArgumentTypeError("label must not be empty")
        path = Path(path_text.strip())
        if path.is_dir():
            path = path / "monthly_exit_timing_metrics.csv"
        pairs.append((label, path))
    if not pairs:
        raise argparse.ArgumentTypeError("at least one --monthly-metrics is required")
    return pairs


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def normalize_monthly_metrics(label: str, path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["source"] = label
    output["source_path"] = str(path)
    output["role"] = output["role"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["candidate"] = output["candidate"].astype(str)
    if "variant" not in output.columns:
        output["variant"] = "base"
    output["variant"] = output["variant"].astype(str)
    output["total_adjusted_pnl"] = numeric_series(output, "total_adjusted_pnl")
    output["trade_count"] = numeric_series(output, "trade_count")
    output["max_drawdown"] = numeric_series(output, "max_drawdown")
    output["long_trade_count"] = numeric_series(output, "long_trade_count")
    output["short_trade_count"] = numeric_series(output, "short_trade_count")
    if "max_side_trade_share" in output.columns:
        output["max_side_trade_share"] = numeric_series(output, "max_side_trade_share")
    else:
        trades = output["trade_count"].replace(0.0, np.nan)
        long_share = output["long_trade_count"] / trades
        short_share = output["short_trade_count"] / trades
        output["max_side_trade_share"] = pd.concat([long_share, short_share], axis=1).max(axis=1).fillna(0.0)
    return output


def load_monthly_metrics(pairs: list[tuple[str, Path]]) -> pd.DataFrame:
    frames = [normalize_monthly_metrics(label, path) for label, path in pairs]
    return pd.concat(frames, ignore_index=True)


def summarize_role_rows(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["source", "variant", "candidate", "role"]
    for key, group in monthly.groupby(group_columns, dropna=False):
        source, variant, candidate, role = key
        adjusted = group["total_adjusted_pnl"].astype(float)
        trades = group["trade_count"].astype(float)
        rows.append(
            {
                "source": source,
                "variant": variant,
                "candidate": candidate,
                "role": role,
                "month_count": int(group["month"].nunique()),
                "active_months": int((trades > 0).sum()),
                "role_total_pnl": float(adjusted.sum()),
                "role_month_min_pnl": float(adjusted.min()),
                "role_trade_count": int(trades.sum()),
                "role_month_trade_min": int(trades.min()),
                "role_max_drawdown": float(group["max_drawdown"].astype(float).max()),
            }
        )
    return pd.DataFrame(rows).sort_values(group_columns).reset_index(drop=True)


def summarize_candidates(
    monthly: pd.DataFrame,
    *,
    min_total_pnl: float,
    min_role_total_pnl: float,
    min_month_pnl: float,
    min_role_trades: int,
    min_month_trades: int,
    max_side_trade_share: float,
    role_floor_penalty: float,
    month_floor_penalty: float,
    drawdown_penalty: float,
    trade_support_penalty: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["source", "variant", "candidate"]
    for key, group in monthly.groupby(group_columns, dropna=False):
        source, variant, candidate = key
        role_totals = group.groupby("role")["total_adjusted_pnl"].sum()
        role_trades = group.groupby("role")["trade_count"].sum()
        month_pnl = group["total_adjusted_pnl"].astype(float)
        month_trades = group["trade_count"].astype(float)
        total_pnl = float(month_pnl.sum())
        role_min = float(role_totals.min())
        month_min = float(month_pnl.min())
        role_trade_min = int(role_trades.min())
        month_trade_min = int(month_trades.min())
        total_trades = int(month_trades.sum())
        long_trades = int(group["long_trade_count"].astype(float).sum())
        short_trades = int(group["short_trade_count"].astype(float).sum())
        overall_side_share = (
            max(long_trades, short_trades) / total_trades if total_trades else 0.0
        )
        observed_side_share = float(
            max(overall_side_share, group["max_side_trade_share"].astype(float).max())
        )
        role_floor_breach = max(0.0, min_role_total_pnl - role_min)
        month_floor_breach = max(0.0, min_month_pnl - month_min)
        total_floor_breach = max(0.0, min_total_pnl - total_pnl)
        role_trade_shortfall = max(0, min_role_trades - role_trade_min)
        month_trade_shortfall = max(0, min_month_trades - month_trade_min)
        support_shortfall = role_trade_shortfall + month_trade_shortfall
        utility = (
            total_pnl
            - role_floor_penalty * role_floor_breach
            - month_floor_penalty * month_floor_breach
            - drawdown_penalty * float(group["max_drawdown"].astype(float).max())
            - trade_support_penalty * support_shortfall
            - role_floor_penalty * total_floor_breach
        )
        blockers: list[str] = []
        if total_pnl < min_total_pnl:
            blockers.append("total_pnl_below_floor")
        if role_min < min_role_total_pnl:
            blockers.append("role_total_pnl_below_floor")
        if month_min < min_month_pnl:
            blockers.append("month_pnl_below_floor")
        if role_trade_min < min_role_trades:
            blockers.append("role_trades_low")
        if month_trade_min < min_month_trades:
            blockers.append("month_trades_low")
        if observed_side_share > max_side_trade_share:
            blockers.append("side_share_high")
        rows.append(
            {
                "source": source,
                "variant": variant,
                "candidate": candidate,
                "role_count": int(role_totals.shape[0]),
                "positive_role_count": int((role_totals > 0).sum()),
                "active_role_count": int((role_trades > 0).sum()),
                "total_pnl": total_pnl,
                "role_total_pnl_min": role_min,
                "month_pnl_min": month_min,
                "trade_count": total_trades,
                "role_trade_count_min": role_trade_min,
                "month_trade_count_min": month_trade_min,
                "max_drawdown": float(group["max_drawdown"].astype(float).max()),
                "overall_side_trade_share": float(overall_side_share),
                "observed_max_side_trade_share": observed_side_share,
                "role_floor_breach": role_floor_breach,
                "month_floor_breach": month_floor_breach,
                "total_floor_breach": total_floor_breach,
                "support_shortfall": support_shortfall,
                "floor_aware_utility": float(utility),
                "selector_pass": not blockers,
                "blockers": ",".join(blockers),
            }
        )
    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary
    return summary.sort_values(
        [
            "selector_pass",
            "role_total_pnl_min",
            "month_pnl_min",
            "floor_aware_utility",
            "total_pnl",
            "trade_count",
        ],
        ascending=[False, False, False, False, False, False],
    ).reset_index(drop=True)


def worst_months(monthly: pd.DataFrame, *, top_n: int) -> pd.DataFrame:
    return (
        monthly.sort_values(["source", "variant", "candidate", "total_adjusted_pnl"])
        .groupby(["source", "variant", "candidate"], dropna=False)
        .head(top_n)
        .reset_index(drop=True)
    )


def select_policy(summary: pd.DataFrame) -> dict[str, Any]:
    if summary.empty:
        return {"selected": "NoTrade", "reason": "empty_summary"}
    eligible = summary[summary["selector_pass"].astype(bool)]
    if not eligible.empty:
        row = eligible.iloc[0].to_dict()
        return {
            "selected": row["candidate"],
            "source": row["source"],
            "variant": row["variant"],
            "reason": "strict_floor_gates_passed",
            "row": row,
        }
    row = summary.iloc[0].to_dict()
    return {
        "selected": "NoTrade",
        "reason": "no_candidate_passed_stateful_floor_gates",
        "diagnostic_best_source": row["source"],
        "diagnostic_best_variant": row["variant"],
        "diagnostic_best_candidate": row["candidate"],
        "diagnostic_best_blockers": row["blockers"],
        "diagnostic_best_row": row,
    }


def run_selector(args: argparse.Namespace) -> Path:
    monthly_inputs = parse_labeled_paths(args.monthly_metrics)
    monthly = load_monthly_metrics(monthly_inputs)
    role_summary = summarize_role_rows(monthly)
    candidate_summary = summarize_candidates(
        monthly,
        min_total_pnl=args.min_total_pnl,
        min_role_total_pnl=args.min_role_total_pnl,
        min_month_pnl=args.min_month_pnl,
        min_role_trades=args.min_role_trades,
        min_month_trades=args.min_month_trades,
        max_side_trade_share=args.max_side_trade_share,
        role_floor_penalty=args.role_floor_penalty,
        month_floor_penalty=args.month_floor_penalty,
        drawdown_penalty=args.drawdown_penalty,
        trade_support_penalty=args.trade_support_penalty,
    )
    selected = select_policy(candidate_summary)

    run_dir = make_run_dir(args.output_dir, args.label)
    monthly.to_csv(run_dir / "stateful_floor_monthly_inputs.csv", index=False)
    role_summary.to_csv(run_dir / "stateful_floor_role_summary.csv", index=False)
    candidate_summary.to_csv(run_dir / "stateful_floor_candidate_summary.csv", index=False)
    worst_months(monthly, top_n=args.worst_month_count).to_csv(
        run_dir / "stateful_floor_worst_months.csv",
        index=False,
    )
    (run_dir / "selected_policy.json").write_text(
        json.dumps(selected, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    config = {
        "monthly_metrics": monthly_inputs,
        "min_total_pnl": args.min_total_pnl,
        "min_role_total_pnl": args.min_role_total_pnl,
        "min_month_pnl": args.min_month_pnl,
        "min_role_trades": args.min_role_trades,
        "min_month_trades": args.min_month_trades,
        "max_side_trade_share": args.max_side_trade_share,
        "role_floor_penalty": args.role_floor_penalty,
        "month_floor_penalty": args.month_floor_penalty,
        "drawdown_penalty": args.drawdown_penalty,
        "trade_support_penalty": args.trade_support_penalty,
        "worst_month_count": args.worst_month_count,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Stateful floor candidate summary:")
    print(
        candidate_summary[
            [
                "source",
                "variant",
                "candidate",
                "selector_pass",
                "total_pnl",
                "role_total_pnl_min",
                "month_pnl_min",
                "trade_count",
                "floor_aware_utility",
                "blockers",
            ]
        ]
        .head(args.print_top)
        .to_string(index=False)
    )
    print(f"selected: {selected['selected']}")
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monthly-metrics", action="append", required=True)
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-month-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-trades", type=int, default=4)
    parser.add_argument("--min-month-trades", type=int, default=1)
    parser.add_argument("--max-side-trade-share", type=float, default=0.95)
    parser.add_argument("--role-floor-penalty", type=float, default=25.0)
    parser.add_argument("--month-floor-penalty", type=float, default=15.0)
    parser.add_argument("--drawdown-penalty", type=float, default=0.0)
    parser.add_argument("--trade-support-penalty", type=float, default=5.0)
    parser.add_argument("--worst-month-count", type=int, default=5)
    parser.add_argument("--print-top", type=int, default=12)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_stateful_floor_meta_selector")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_selector(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
