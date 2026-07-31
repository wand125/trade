#!/usr/bin/env python3
"""Estimate repair targets for standard admission blockers."""

from __future__ import annotations

import argparse
import json
import math
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
from entry_ev_supervised_shrinkage_policy_inputs import (  # noqa: E402
    local_json_default,
    parse_csv,
)


REQUIRED_COLUMNS = {
    "role",
    "month",
    "candidate",
    "total_adjusted_pnl",
    "trade_count",
}
GROUP_COLUMNS = ["source", "variant", "candidate", "entry_block_rule"]


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
    if "entry_block_rule" not in output.columns:
        output["entry_block_rule"] = "none"
    output["entry_block_rule"] = output["entry_block_rule"].astype(str)
    output["total_adjusted_pnl"] = numeric_series(output, "total_adjusted_pnl")
    output["trade_count"] = numeric_series(output, "trade_count")
    output["long_trade_count"] = numeric_series(output, "long_trade_count")
    output["short_trade_count"] = numeric_series(output, "short_trade_count")
    if "max_side_trade_share" in output.columns:
        output["max_side_trade_share"] = numeric_series(output, "max_side_trade_share")
    else:
        trades = output["trade_count"].replace(0.0, np.nan)
        output["max_side_trade_share"] = pd.concat(
            [output["long_trade_count"] / trades, output["short_trade_count"] / trades],
            axis=1,
        ).max(axis=1).fillna(0.0)
    return output


def load_monthly_metrics(pairs: list[tuple[str, Path]]) -> pd.DataFrame:
    if not pairs:
        raise ValueError("at least one monthly metrics path is required")
    return pd.concat(
        [normalize_monthly_metrics(label, path) for label, path in pairs],
        ignore_index=True,
    )


def apply_filters(
    frame: pd.DataFrame,
    *,
    variant_contains: str,
    candidates: list[str],
    entry_block_rules: list[str],
) -> pd.DataFrame:
    output = frame.copy()
    if variant_contains:
        output = output[output["variant"].astype(str).str.contains(variant_contains, regex=False)]
    if candidates:
        output = output[output["candidate"].astype(str).isin(candidates)]
    if entry_block_rules:
        output = output[output["entry_block_rule"].astype(str).isin(entry_block_rules)]
    if output.empty:
        raise ValueError("filters removed all monthly metrics rows")
    return output.reset_index(drop=True)


def side_share(long_count: int, short_count: int) -> float:
    total = long_count + short_count
    if total <= 0:
        return 0.0
    return max(long_count, short_count) / total


def minimal_side_balanced_additions(
    *,
    long_count: int,
    short_count: int,
    min_trades: int,
    max_side_trade_share: float,
) -> dict[str, Any]:
    if not 0.0 < max_side_trade_share <= 1.0:
        raise ValueError("max_side_trade_share must be in (0, 1]")
    if max_side_trade_share >= 1.0:
        extra_total = max(0, min_trades - long_count - short_count)
        return {
            "extra_long_needed": 0,
            "extra_short_needed": extra_total,
            "extra_trades_needed": extra_total,
            "post_long_trade_count": long_count,
            "post_short_trade_count": short_count + extra_total,
            "post_max_side_trade_share": side_share(long_count, short_count + extra_total),
        }

    existing_total = long_count + short_count
    majority = max(long_count, short_count, 1)
    side_extra_bound = max(0, math.ceil(majority / max_side_trade_share) - existing_total)
    cap = max(min_trades, existing_total + side_extra_bound + 5, 20)
    best: tuple[int, int] | None = None
    for add_total in range(0, cap + 1):
        for add_long in range(add_total + 1):
            add_short = add_total - add_long
            new_long = long_count + add_long
            new_short = short_count + add_short
            new_total = new_long + new_short
            if new_total < min_trades:
                continue
            if new_total > 0 and side_share(new_long, new_short) > max_side_trade_share:
                continue
            best = (add_long, add_short)
            break
        if best is not None:
            break
    if best is None:
        raise ValueError("failed to find side-balanced additions")
    add_long, add_short = best
    post_long = long_count + add_long
    post_short = short_count + add_short
    return {
        "extra_long_needed": int(add_long),
        "extra_short_needed": int(add_short),
        "extra_trades_needed": int(add_long + add_short),
        "post_long_trade_count": int(post_long),
        "post_short_trade_count": int(post_short),
        "post_max_side_trade_share": float(side_share(post_long, post_short)),
    }


def classify_floor_breach(row: pd.Series, *, shallow_month_floor: float) -> str:
    pnl = float(row["total_adjusted_pnl"])
    if pnl >= 0.0:
        return "pass"
    if bool(row["support_limited_negative_month"]):
        return "support_limited"
    if pnl >= shallow_month_floor:
        return "shallow"
    return "structural"


def build_month_targets(
    monthly: pd.DataFrame,
    *,
    month_floor: float,
    min_month_trades: int,
    max_side_trade_share: float,
    shallow_month_floor: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in monthly.iterrows():
        long_count = int(float(row["long_trade_count"]))
        short_count = int(float(row["short_trade_count"]))
        addition = minimal_side_balanced_additions(
            long_count=long_count,
            short_count=short_count,
            min_trades=min_month_trades,
            max_side_trade_share=max_side_trade_share,
        )
        pnl = float(row["total_adjusted_pnl"])
        trade_count = int(float(row["trade_count"]))
        row_out = row.to_dict()
        row_out.update(addition)
        row_out["month_pnl_hurdle"] = float(max(0.0, month_floor - pnl))
        row_out["month_trade_shortfall"] = int(max(0, min_month_trades - trade_count))
        row_out["side_share_excess"] = float(
            max(0.0, float(row["max_side_trade_share"]) - max_side_trade_share)
        )
        row_out["support_limited_month"] = bool(
            row_out["month_trade_shortfall"] > 0
            or row_out["side_share_excess"] > 0
            or row_out["extra_trades_needed"] > 0
        )
        row_out["support_limited_negative_month"] = bool(
            pnl < month_floor and row_out["support_limited_month"]
        )
        row_out["floor_breach_class"] = classify_floor_breach(
            pd.Series(row_out),
            shallow_month_floor=shallow_month_floor,
        )
        rows.append(row_out)
    return pd.DataFrame(rows)


def build_role_targets(
    month_targets: pd.DataFrame,
    *,
    min_role_trades: int,
    min_role_total_pnl: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in month_targets.groupby([*GROUP_COLUMNS, "role"], dropna=False):
        source, variant, candidate, entry_block_rule, role = key
        role_pnl = float(group["total_adjusted_pnl"].sum())
        trade_count = int(group["trade_count"].astype(float).sum())
        post_month_trades = int(
            trade_count + group["extra_trades_needed"].astype(int).sum()
        )
        rows.append(
            {
                "source": source,
                "variant": variant,
                "candidate": candidate,
                "entry_block_rule": entry_block_rule,
                "role": role,
                "role_total_pnl": role_pnl,
                "role_pnl_hurdle": float(max(0.0, min_role_total_pnl - role_pnl)),
                "role_trade_count": trade_count,
                "role_trade_shortfall": int(max(0, min_role_trades - trade_count)),
                "post_month_repair_role_trade_count": post_month_trades,
                "post_month_repair_role_trade_shortfall": int(
                    max(0, min_role_trades - post_month_trades)
                ),
                "negative_month_count": int(group["total_adjusted_pnl"].lt(0.0).sum()),
                "support_limited_negative_month_count": int(
                    group["support_limited_negative_month"].astype(bool).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def build_candidate_summary(
    month_targets: pd.DataFrame,
    role_targets: pd.DataFrame,
    *,
    min_total_pnl: float,
    min_role_total_pnl: float,
    month_floor: float,
    min_role_trades: int,
    min_month_trades: int,
    max_side_trade_share: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in month_targets.groupby(GROUP_COLUMNS, dropna=False):
        source, variant, candidate, entry_block_rule = key
        role_group = role_targets[
            role_targets["source"].astype(str).eq(str(source))
            & role_targets["variant"].astype(str).eq(str(variant))
            & role_targets["candidate"].astype(str).eq(str(candidate))
            & role_targets["entry_block_rule"].astype(str).eq(str(entry_block_rule))
        ]
        total_pnl = float(group["total_adjusted_pnl"].sum())
        trade_count = int(group["trade_count"].astype(float).sum())
        long_count = int(group["long_trade_count"].astype(float).sum())
        short_count = int(group["short_trade_count"].astype(float).sum())
        monthly_extra = int(group["extra_trades_needed"].astype(int).sum())
        post_long = int(group["post_long_trade_count"].astype(int).sum())
        post_short = int(group["post_short_trade_count"].astype(int).sum())
        post_month_side_share = side_share(post_long, post_short)
        role_shortfall_after_month = int(
            role_group["post_month_repair_role_trade_shortfall"].astype(int).sum()
        )
        summary = {
            "source": source,
            "variant": variant,
            "candidate": candidate,
            "entry_block_rule": entry_block_rule,
            "total_pnl": total_pnl,
            "total_pnl_hurdle": float(max(0.0, min_total_pnl - total_pnl)),
            "role_pnl_hurdle_sum": float(role_group["role_pnl_hurdle"].sum()),
            "month_pnl_hurdle_sum": float(group["month_pnl_hurdle"].sum()),
            "trade_count": trade_count,
            "role_trade_count_min": int(role_group["role_trade_count"].min()),
            "month_trade_count_min": int(group["trade_count"].astype(float).min()),
            "overall_side_trade_share": float(side_share(long_count, short_count)),
            "observed_max_side_trade_share": float(group["max_side_trade_share"].max()),
            "negative_month_count": int(group["total_adjusted_pnl"].lt(month_floor).sum()),
            "support_limited_negative_month_count": int(
                group["support_limited_negative_month"].astype(bool).sum()
            ),
            "shallow_negative_month_count": int(
                group["floor_breach_class"].astype(str).eq("shallow").sum()
            ),
            "structural_negative_month_count": int(
                group["floor_breach_class"].astype(str).eq("structural").sum()
            ),
            "monthly_support_extra_trades": monthly_extra,
            "monthly_support_extra_long": int(group["extra_long_needed"].astype(int).sum()),
            "monthly_support_extra_short": int(group["extra_short_needed"].astype(int).sum()),
            "post_month_repair_overall_side_share": float(post_month_side_share),
            "role_support_extra_after_month_repair": role_shortfall_after_month,
        }
        blockers: list[str] = []
        if summary["total_pnl"] < min_total_pnl:
            blockers.append("total_pnl_below_floor")
        if role_group["role_total_pnl"].min() < min_role_total_pnl:
            blockers.append("role_total_pnl_below_floor")
        if group["total_adjusted_pnl"].min() < month_floor:
            blockers.append("month_pnl_below_floor")
        if summary["role_trade_count_min"] < min_role_trades:
            blockers.append("role_trades_low")
        if summary["month_trade_count_min"] < min_month_trades:
            blockers.append("month_trades_low")
        if summary["observed_max_side_trade_share"] > max_side_trade_share:
            blockers.append("side_share_high")
        summary["standard_blockers"] = ",".join(blockers)
        summary["standard_pass"] = not blockers
        rows.append(summary)
    return pd.DataFrame(rows).sort_values(
        [
            "standard_pass",
            "month_pnl_hurdle_sum",
            "monthly_support_extra_trades",
            "total_pnl",
        ],
        ascending=[False, True, True, False],
    )


def run_diagnostics(args: argparse.Namespace) -> Path:
    monthly = load_monthly_metrics(parse_labeled_paths(args.monthly_metrics))
    monthly = apply_filters(
        monthly,
        variant_contains=args.variant_contains,
        candidates=parse_csv(args.candidates),
        entry_block_rules=parse_csv(args.entry_block_rules),
    )
    month_targets = build_month_targets(
        monthly,
        month_floor=args.month_floor,
        min_month_trades=args.min_month_trades,
        max_side_trade_share=args.max_side_trade_share,
        shallow_month_floor=args.shallow_month_floor,
    )
    role_targets = build_role_targets(
        month_targets,
        min_role_trades=args.min_role_trades,
        min_role_total_pnl=args.min_role_total_pnl,
    )
    candidate_summary = build_candidate_summary(
        month_targets,
        role_targets,
        min_total_pnl=args.min_total_pnl,
        min_role_total_pnl=args.min_role_total_pnl,
        month_floor=args.month_floor,
        min_role_trades=args.min_role_trades,
        min_month_trades=args.min_month_trades,
        max_side_trade_share=args.max_side_trade_share,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    month_targets.to_csv(run_dir / "admission_repair_month_targets.csv", index=False)
    role_targets.to_csv(run_dir / "admission_repair_role_targets.csv", index=False)
    candidate_summary.to_csv(
        run_dir / "admission_repair_candidate_summary.csv",
        index=False,
    )
    config = {
        "monthly_metrics": parse_labeled_paths(args.monthly_metrics),
        "variant_contains": args.variant_contains,
        "candidates": parse_csv(args.candidates),
        "entry_block_rules": parse_csv(args.entry_block_rules),
        "min_total_pnl": args.min_total_pnl,
        "min_role_total_pnl": args.min_role_total_pnl,
        "month_floor": args.month_floor,
        "shallow_month_floor": args.shallow_month_floor,
        "min_role_trades": args.min_role_trades,
        "min_month_trades": args.min_month_trades,
        "max_side_trade_share": args.max_side_trade_share,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Admission repair candidate summary:")
    print(
        candidate_summary[
            [
                "source",
                "entry_block_rule",
                "total_pnl",
                "month_pnl_hurdle_sum",
                "monthly_support_extra_trades",
                "monthly_support_extra_long",
                "monthly_support_extra_short",
                "negative_month_count",
                "support_limited_negative_month_count",
                "standard_blockers",
            ]
        ].head(30).to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monthly-metrics", action="append", required=True)
    parser.add_argument("--variant-contains", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--entry-block-rules", default="")
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--month-floor", type=float, default=0.0)
    parser.add_argument("--shallow-month-floor", type=float, default=-1.0)
    parser.add_argument("--min-role-trades", type=int, default=4)
    parser.add_argument("--min-month-trades", type=int, default=1)
    parser.add_argument("--max-side-trade-share", type=float, default=0.95)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_admission_repair_target_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
