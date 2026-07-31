#!/usr/bin/env python3
"""Support-aware admission diagnostics for stateful policy candidates."""

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

from entry_ev_stateful_floor_meta_selector import parse_labeled_paths  # noqa: E402
from entry_ev_supervised_shrinkage_policy_inputs import local_json_default  # noqa: E402


REQUIRED_COLUMNS = {
    "role",
    "month",
    "candidate",
    "total_adjusted_pnl",
    "trade_count",
}


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
    output["long_trade_count"] = numeric_series(output, "long_trade_count")
    output["short_trade_count"] = numeric_series(output, "short_trade_count")
    output["max_drawdown"] = numeric_series(output, "max_drawdown")
    if "max_side_trade_share" in output.columns:
        output["max_side_trade_share"] = numeric_series(output, "max_side_trade_share")
    else:
        trades = output["trade_count"].replace(0.0, np.nan)
        side_share = pd.concat(
            [output["long_trade_count"] / trades, output["short_trade_count"] / trades],
            axis=1,
        ).max(axis=1)
        output["max_side_trade_share"] = side_share.fillna(0.0)
    return output


def load_monthly_metrics(pairs: list[tuple[str, Path]]) -> pd.DataFrame:
    frames = [normalize_monthly_metrics(label, path) for label, path in pairs]
    if not frames:
        raise ValueError("at least one monthly metrics path is required")
    return pd.concat(frames, ignore_index=True)


def add_floor_breach_classification(
    monthly: pd.DataFrame,
    *,
    month_floor: float,
    thin_month_trade_threshold: int,
    concentrated_side_share_threshold: float,
    shallow_month_floor: float,
) -> pd.DataFrame:
    output = monthly.copy()
    output["month_floor_breach"] = output["total_adjusted_pnl"].lt(month_floor)
    output["thin_month"] = output["trade_count"].lt(thin_month_trade_threshold)
    output["side_concentrated_month"] = output["max_side_trade_share"].gt(
        concentrated_side_share_threshold
    )
    output["support_limited_negative_month"] = (
        output["month_floor_breach"]
        & (output["thin_month"] | output["side_concentrated_month"])
    )
    output["shallow_negative_month"] = (
        output["month_floor_breach"]
        & ~output["support_limited_negative_month"]
        & output["total_adjusted_pnl"].ge(shallow_month_floor)
    )
    output["structural_negative_month"] = (
        output["month_floor_breach"]
        & ~output["support_limited_negative_month"]
        & ~output["shallow_negative_month"]
    )
    conditions = [
        ~output["month_floor_breach"],
        output["support_limited_negative_month"],
        output["shallow_negative_month"],
        output["structural_negative_month"],
    ]
    choices = ["pass", "support_limited", "shallow", "structural"]
    output["floor_breach_class"] = np.select(conditions, choices, default="unknown")
    return output


def _count_true(series: pd.Series) -> int:
    return int(series.fillna(False).astype(bool).sum())


def _join_blockers(blockers: list[str]) -> str:
    return ",".join(blockers)


def summarize_support_aware_candidates(
    monthly: pd.DataFrame,
    *,
    min_total_pnl: float,
    min_role_total_pnl: float,
    month_floor: float,
    shallow_month_floor: float,
    min_role_trades: int,
    min_month_trades: int,
    max_side_trade_share: float,
    allow_shallow_negative_months: int,
    allow_support_limited_negative_months: int,
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
        total_trades = int(month_trades.sum())
        role_trade_min = int(role_trades.min())
        month_trade_min = int(month_trades.min())
        long_trades = int(group["long_trade_count"].astype(float).sum())
        short_trades = int(group["short_trade_count"].astype(float).sum())
        overall_side_share = max(long_trades, short_trades) / total_trades if total_trades else 0.0
        observed_side_share = float(
            max(overall_side_share, group["max_side_trade_share"].astype(float).max())
        )

        strict_blockers: list[str] = []
        if total_pnl < min_total_pnl:
            strict_blockers.append("total_pnl_below_floor")
        if role_min < min_role_total_pnl:
            strict_blockers.append("role_total_pnl_below_floor")
        if month_min < month_floor:
            strict_blockers.append("month_pnl_below_floor")
        if role_trade_min < min_role_trades:
            strict_blockers.append("role_trades_low")
        if month_trade_min < min_month_trades:
            strict_blockers.append("month_trades_low")
        if observed_side_share > max_side_trade_share:
            strict_blockers.append("side_share_high")

        support_limited_count = _count_true(group["support_limited_negative_month"])
        shallow_count = _count_true(group["shallow_negative_month"])
        structural_count = _count_true(group["structural_negative_month"])
        floor_breach_count = _count_true(group["month_floor_breach"])

        support_blockers: list[str] = []
        if total_pnl < min_total_pnl:
            support_blockers.append("total_pnl_below_floor")
        if role_min < min_role_total_pnl:
            support_blockers.append("role_total_pnl_below_floor")
        if structural_count > 0:
            support_blockers.append("structural_negative_months")
        if shallow_count > allow_shallow_negative_months:
            support_blockers.append("too_many_shallow_negative_months")
        if support_limited_count > allow_support_limited_negative_months:
            support_blockers.append("too_many_support_limited_negative_months")

        support_aware_floor_pass = not support_blockers
        standard_pass = not strict_blockers
        diagnostic_status = (
            "standard_pass"
            if standard_pass
            else "support_aware_only"
            if support_aware_floor_pass
            else "blocked"
        )
        rows.append(
            {
                "source": source,
                "variant": variant,
                "candidate": candidate,
                "diagnostic_status": diagnostic_status,
                "standard_pass": standard_pass,
                "support_aware_floor_pass": support_aware_floor_pass,
                "total_pnl": total_pnl,
                "role_total_pnl_min": role_min,
                "month_pnl_min": month_min,
                "shallow_month_floor": shallow_month_floor,
                "trade_count": total_trades,
                "role_trade_count_min": role_trade_min,
                "month_trade_count_min": month_trade_min,
                "overall_side_trade_share": float(overall_side_share),
                "observed_max_side_trade_share": observed_side_share,
                "negative_month_count": floor_breach_count,
                "support_limited_negative_month_count": support_limited_count,
                "shallow_negative_month_count": shallow_count,
                "structural_negative_month_count": structural_count,
                "max_drawdown": float(group["max_drawdown"].astype(float).max()),
                "strict_blockers": _join_blockers(strict_blockers),
                "support_aware_blockers": _join_blockers(support_blockers),
            }
        )
    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary
    return summary.sort_values(
        [
            "standard_pass",
            "support_aware_floor_pass",
            "structural_negative_month_count",
            "role_total_pnl_min",
            "month_pnl_min",
            "total_pnl",
            "trade_count",
        ],
        ascending=[False, False, True, False, False, False, False],
    ).reset_index(drop=True)


def worst_classified_months(monthly: pd.DataFrame, *, top_n: int) -> pd.DataFrame:
    return (
        monthly.sort_values(["source", "variant", "candidate", "total_adjusted_pnl"])
        .groupby(["source", "variant", "candidate"], dropna=False)
        .head(top_n)
        .reset_index(drop=True)
    )


def select_diagnostic(summary: pd.DataFrame) -> dict[str, Any]:
    if summary.empty:
        return {"selected": "NoTrade", "reason": "empty_summary"}
    standard = summary[summary["standard_pass"].astype(bool)]
    if not standard.empty:
        row = standard.iloc[0].to_dict()
        return {
            "selected": row["candidate"],
            "source": row["source"],
            "variant": row["variant"],
            "reason": "strict_standard_pass",
            "row": row,
        }
    support_aware = summary[summary["support_aware_floor_pass"].astype(bool)]
    if not support_aware.empty:
        row = support_aware.iloc[0].to_dict()
        return {
            "selected": "NoTrade",
            "reason": "support_aware_diagnostic_only",
            "diagnostic_best_source": row["source"],
            "diagnostic_best_variant": row["variant"],
            "diagnostic_best_candidate": row["candidate"],
            "diagnostic_best_row": row,
        }
    row = summary.iloc[0].to_dict()
    return {
        "selected": "NoTrade",
        "reason": "no_candidate_passed_support_aware_floor",
        "diagnostic_best_source": row["source"],
        "diagnostic_best_variant": row["variant"],
        "diagnostic_best_candidate": row["candidate"],
        "diagnostic_best_row": row,
    }


def run_diagnostics(args: argparse.Namespace) -> Path:
    monthly_inputs = parse_labeled_paths(args.monthly_metrics)
    monthly = load_monthly_metrics(monthly_inputs)
    classified = add_floor_breach_classification(
        monthly,
        month_floor=args.month_floor,
        thin_month_trade_threshold=args.thin_month_trade_threshold,
        concentrated_side_share_threshold=args.concentrated_side_share_threshold,
        shallow_month_floor=args.shallow_month_floor,
    )
    summary = summarize_support_aware_candidates(
        classified,
        min_total_pnl=args.min_total_pnl,
        min_role_total_pnl=args.min_role_total_pnl,
        month_floor=args.month_floor,
        shallow_month_floor=args.shallow_month_floor,
        min_role_trades=args.min_role_trades,
        min_month_trades=args.min_month_trades,
        max_side_trade_share=args.max_side_trade_share,
        allow_shallow_negative_months=args.allow_shallow_negative_months,
        allow_support_limited_negative_months=args.allow_support_limited_negative_months,
    )
    selected = select_diagnostic(summary)

    run_dir = make_run_dir(args.output_dir, args.label)
    classified.to_csv(run_dir / "support_aware_monthly_inputs.csv", index=False)
    summary.to_csv(run_dir / "support_aware_candidate_summary.csv", index=False)
    worst_classified_months(classified, top_n=args.worst_month_count).to_csv(
        run_dir / "support_aware_worst_months.csv",
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
        "month_floor": args.month_floor,
        "shallow_month_floor": args.shallow_month_floor,
        "thin_month_trade_threshold": args.thin_month_trade_threshold,
        "concentrated_side_share_threshold": args.concentrated_side_share_threshold,
        "min_role_trades": args.min_role_trades,
        "min_month_trades": args.min_month_trades,
        "max_side_trade_share": args.max_side_trade_share,
        "allow_shallow_negative_months": args.allow_shallow_negative_months,
        "allow_support_limited_negative_months": args.allow_support_limited_negative_months,
        "worst_month_count": args.worst_month_count,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Support-aware admission summary:")
    print(
        summary[
            [
                "source",
                "variant",
                "candidate",
                "diagnostic_status",
                "standard_pass",
                "support_aware_floor_pass",
                "total_pnl",
                "role_total_pnl_min",
                "month_pnl_min",
                "negative_month_count",
                "support_limited_negative_month_count",
                "shallow_negative_month_count",
                "structural_negative_month_count",
                "strict_blockers",
                "support_aware_blockers",
            ]
        ]
        .head(args.print_top)
        .to_string(index=False)
    )
    print(f"selected: {selected['selected']}")
    print(f"reason: {selected['reason']}")
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monthly-metrics", action="append", required=True)
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--month-floor", type=float, default=0.0)
    parser.add_argument("--shallow-month-floor", type=float, default=-1.0)
    parser.add_argument("--thin-month-trade-threshold", type=int, default=5)
    parser.add_argument("--concentrated-side-share-threshold", type=float, default=0.95)
    parser.add_argument("--min-role-trades", type=int, default=4)
    parser.add_argument("--min-month-trades", type=int, default=1)
    parser.add_argument("--max-side-trade-share", type=float, default=0.95)
    parser.add_argument("--allow-shallow-negative-months", type=int, default=1)
    parser.add_argument("--allow-support-limited-negative-months", type=int, default=3)
    parser.add_argument("--worst-month-count", type=int, default=5)
    parser.add_argument("--print-top", type=int, default=12)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_stateful_support_aware_admission")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
