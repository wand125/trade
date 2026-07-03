#!/usr/bin/env python3
"""Inventory support-sufficient and support-limited negative months across selector outputs."""

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

from entry_ev_admission_repair_target_diagnostics import (  # noqa: E402
    GROUP_COLUMNS,
    build_month_targets,
    normalize_monthly_metrics,
)
from entry_ev_supervised_shrinkage_policy_inputs import local_json_default  # noqa: E402
from entry_ev_thin_month_opposite_candidate_diagnostics import numeric_series  # noqa: E402


DEFAULT_PATTERN = "*selector_monthly_metrics.csv"


def discover_metric_paths(root: Path, *, pattern: str) -> list[Path]:
    return sorted(path for path in root.rglob(pattern) if path.is_file())


def source_label(path: Path, root: Path) -> str:
    try:
        return str(path.parent.relative_to(root))
    except ValueError:
        return path.parent.name


def load_metric_targets(
    paths: list[Path],
    *,
    root: Path,
    month_floor: float,
    min_month_trades: int,
    max_side_trade_share: float,
    shallow_month_floor: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    source_rows: list[dict[str, Any]] = []
    for path in paths:
        label = source_label(path, root)
        try:
            monthly = normalize_monthly_metrics(label, path)
            targets = build_month_targets(
                monthly,
                month_floor=month_floor,
                min_month_trades=min_month_trades,
                max_side_trade_share=max_side_trade_share,
                shallow_month_floor=shallow_month_floor,
            )
            targets["metric_path"] = str(path)
            targets["metric_parent"] = label
            frames.append(targets)
            source_rows.append(
                {
                    "metric_path": str(path),
                    "metric_parent": label,
                    "load_status": "ok",
                    "row_count": int(len(targets)),
                    "error": "",
                }
            )
        except Exception as exc:  # pragma: no cover - diagnostic inventory should keep scanning.
            source_rows.append(
                {
                    "metric_path": str(path),
                    "metric_parent": label,
                    "load_status": "error",
                    "row_count": 0,
                    "error": str(exc),
                }
            )
    targets = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    return targets, pd.DataFrame(source_rows)


def add_negative_flags(targets: pd.DataFrame, *, month_floor: float) -> pd.DataFrame:
    if targets.empty:
        return targets.copy()
    output = targets.copy()
    pnl = numeric_series(output, "total_adjusted_pnl", default=0.0)
    support_limited = output["support_limited_month"].astype(bool)
    output["negative_month"] = pnl.lt(float(month_floor))
    output["support_sufficient_negative_month"] = output["negative_month"] & ~support_limited
    output["support_limited_negative_month"] = output["negative_month"] & support_limited
    output["month_pnl"] = pnl
    output["target_identity"] = (
        output["role"].astype(str)
        + "|"
        + output["family"].astype(str)
        + "|"
        + output["month"].astype(str)
    )
    return output


def summarize_configs(targets: pd.DataFrame) -> pd.DataFrame:
    if targets.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_cols = ["metric_parent", "metric_path", *GROUP_COLUMNS]
    for keys, group in targets.groupby(group_cols, dropna=False):
        negative = group["negative_month"].astype(bool)
        support_sufficient = group["support_sufficient_negative_month"].astype(bool)
        support_limited = group["support_limited_negative_month"].astype(bool)
        rows.append(
            {
                **dict(zip(group_cols, keys, strict=True)),
                "month_row_count": int(len(group)),
                "role_count": int(group["role"].astype(str).nunique()),
                "negative_month_count": int(negative.sum()),
                "support_sufficient_negative_count": int(support_sufficient.sum()),
                "support_limited_negative_count": int(support_limited.sum()),
                "shallow_negative_count": int(
                    group["floor_breach_class"].astype(str).eq("shallow").sum()
                ),
                "structural_negative_count": int(
                    group["floor_breach_class"].astype(str).eq("structural").sum()
                ),
                "min_month_pnl": float(numeric_series(group, "month_pnl").min()),
                "month_pnl_hurdle_sum": float(
                    numeric_series(group, "month_pnl_hurdle", default=0.0).sum()
                ),
                "extra_trades_needed_sum": int(
                    numeric_series(group, "extra_trades_needed", default=0.0).sum()
                ),
                "extra_long_needed_sum": int(
                    numeric_series(group, "extra_long_needed", default=0.0).sum()
                ),
                "extra_short_needed_sum": int(
                    numeric_series(group, "extra_short_needed", default=0.0).sum()
                ),
                "total_adjusted_pnl_sum": float(
                    numeric_series(group, "total_adjusted_pnl", default=0.0).sum()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        [
            "support_sufficient_negative_count",
            "support_limited_negative_count",
            "month_pnl_hurdle_sum",
            "total_adjusted_pnl_sum",
        ],
        ascending=[False, True, True, False],
    )


def summarize_targets(targets: pd.DataFrame) -> pd.DataFrame:
    if targets.empty:
        return pd.DataFrame()
    negative = targets[targets["negative_month"].astype(bool)].copy()
    if negative.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for (role, family, month), group in negative.groupby(["role", "family", "month"], dropna=False):
        support_sufficient = group["support_sufficient_negative_month"].astype(bool)
        support_limited = group["support_limited_negative_month"].astype(bool)
        rows.append(
            {
                "role": str(role),
                "family": str(family),
                "month": str(month),
                "config_count": int(len(group)),
                "support_sufficient_config_count": int(support_sufficient.sum()),
                "support_limited_config_count": int(support_limited.sum()),
                "best_month_pnl": float(numeric_series(group, "month_pnl").max()),
                "worst_month_pnl": float(numeric_series(group, "month_pnl").min()),
                "mean_month_pnl": float(numeric_series(group, "month_pnl").mean()),
                "min_extra_trades_needed": int(
                    numeric_series(group, "extra_trades_needed", default=0.0).min()
                ),
                "min_extra_long_needed": int(
                    numeric_series(group, "extra_long_needed", default=0.0).min()
                ),
                "min_extra_short_needed": int(
                    numeric_series(group, "extra_short_needed", default=0.0).min()
                ),
                "metric_parent_count": int(group["metric_parent"].astype(str).nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        [
            "support_sufficient_config_count",
            "support_limited_config_count",
            "best_month_pnl",
        ],
        ascending=[False, True, False],
    )


def run_diagnostics(args: argparse.Namespace) -> Path:
    scan_root = args.scan_root.resolve()
    paths = discover_metric_paths(scan_root, pattern=args.pattern)
    if args.limit_paths > 0:
        paths = paths[: int(args.limit_paths)]
    targets, sources = load_metric_targets(
        paths,
        root=scan_root,
        month_floor=float(args.month_floor),
        min_month_trades=int(args.min_month_trades),
        max_side_trade_share=float(args.max_side_trade_share),
        shallow_month_floor=float(args.shallow_month_floor),
    )
    targets = add_negative_flags(targets, month_floor=float(args.month_floor))
    config_summary = summarize_configs(targets)
    target_summary = summarize_targets(targets)

    run_dir = make_run_dir(args.output_root, args.run_label)
    sources.to_csv(run_dir / "support_negative_month_source_inventory.csv", index=False)
    targets.to_csv(run_dir / "support_negative_month_inventory.csv", index=False)
    config_summary.to_csv(run_dir / "support_negative_month_config_summary.csv", index=False)
    target_summary.to_csv(run_dir / "support_negative_month_target_summary.csv", index=False)
    meta = {
        "scan_root": scan_root,
        "pattern": args.pattern,
        "path_count": len(paths),
        "month_floor": args.month_floor,
        "shallow_month_floor": args.shallow_month_floor,
        "min_month_trades": args.min_month_trades,
        "max_side_trade_share": args.max_side_trade_share,
        "note": (
            "This is an artifact inventory. Realized monthly PnL is used to label target "
            "sets for research planning only, not as an execution-time feature."
        ),
    }
    (run_dir / "support_negative_month_inventory_meta.json").write_text(
        json.dumps(meta, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Support negative month config summary:")
    if not config_summary.empty:
        print(
            config_summary[
                [
                    "metric_parent",
                    "entry_block_rule",
                    "negative_month_count",
                    "support_sufficient_negative_count",
                    "support_limited_negative_count",
                    "min_month_pnl",
                    "month_pnl_hurdle_sum",
                    "extra_trades_needed_sum",
                ]
            ]
            .head(int(args.print_rows))
            .to_string(index=False)
        )
    print("\nTarget summary:")
    if not target_summary.empty:
        print(target_summary.head(int(args.print_rows)).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-root", type=Path, default=ROOT / "data/reports/backtests")
    parser.add_argument("--pattern", default=DEFAULT_PATTERN)
    parser.add_argument("--month-floor", type=float, default=0.0)
    parser.add_argument("--shallow-month-floor", type=float, default=-1.0)
    parser.add_argument("--min-month-trades", type=int, default=1)
    parser.add_argument("--max-side-trade-share", type=float, default=0.95)
    parser.add_argument("--limit-paths", type=int, default=0)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/reports/backtests")
    parser.add_argument(
        "--run-label",
        default="entry_ev_support_negative_month_inventory_diagnostics",
    )
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
