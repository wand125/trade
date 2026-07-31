#!/usr/bin/env python3
"""Select entry-EV admission candidates without peeking at holdout months."""

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

from trade_data.backtest import (  # noqa: E402
    SWEEP_KEY_COLUMNS,
    json_default,
    make_run_dir,
    normalize_sweep_metrics,
)


def parse_family_sweeps(values: list[str]) -> dict[str, list[Path]]:
    families: dict[str, list[Path]] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError(
                "family sweeps must use family=path1,path2"
            )
        family, raw_paths = value.split("=", 1)
        family = family.strip()
        if not family:
            raise argparse.ArgumentTypeError("family name must not be empty")
        paths = [Path(part.strip()) for part in raw_paths.split(",") if part.strip()]
        if not paths:
            raise argparse.ArgumentTypeError(f"{family} has no sweep paths")
        families.setdefault(family, []).extend(paths)
    return families


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


def read_family_sweeps(families: dict[str, list[Path]]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for family, paths in families.items():
        for path in paths:
            frame = pd.read_csv(path)
            frame = normalize_sweep_metrics(frame, str(path)).copy()
            frame["family"] = family
            frame["sweep_path"] = str(path)
            if "period_start" in frame.columns:
                frame["month"] = (
                    pd.to_datetime(frame["period_start"], utc=True)
                    .dt.strftime("%Y-%m")
                    .astype(str)
                )
            elif "month" not in frame.columns:
                frame["month"] = path.parent.name[-7:]
            frames.append(frame)
    if not frames:
        raise ValueError("at least one sweep metrics file is required")
    return pd.concat(frames, ignore_index=True, sort=False)


def aggregate_validation(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"family", "month", "total_adjusted_pnl", "trade_count", "max_drawdown"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"sweep frame missing columns: {', '.join(missing)}")

    grouped = frame.groupby(["family", *SWEEP_KEY_COLUMNS], dropna=False)
    rows: list[dict[str, object]] = []
    for keys, group in grouped:
        family = keys[0]
        key_values = dict(zip(SWEEP_KEY_COLUMNS, keys[1:], strict=True))
        trade_count = int(group["trade_count"].sum())
        forced_exit_count = (
            int(group["forced_exit_count"].sum())
            if "forced_exit_count" in group.columns
            else 0
        )
        min_monthly_trades = int(group["trade_count"].min())
        max_monthly_trades = int(group["trade_count"].max())
        long_trades = int(group.get("long_trade_count", pd.Series(dtype=float)).sum())
        short_trades = int(group.get("short_trade_count", pd.Series(dtype=float)).sum())
        max_side_trade_share = (
            max(long_trades, short_trades) / trade_count if trade_count > 0 else 0.0
        )
        rows.append(
            {
                "family": family,
                **key_values,
                "months": int(group["month"].nunique()),
                "validation_active_months": int((group["trade_count"] > 0).sum()),
                "validation_total": float(group["total_adjusted_pnl"].sum()),
                "validation_worst": float(group["total_adjusted_pnl"].min()),
                "validation_trades": trade_count,
                "validation_min_monthly_trades": min_monthly_trades,
                "validation_max_monthly_trades": max_monthly_trades,
                "validation_max_dd": float(group["max_drawdown"].max()),
                "validation_forced_exit_count": forced_exit_count,
                "validation_long_trades": long_trades,
                "validation_short_trades": short_trades,
                "validation_max_side_trade_share": float(max_side_trade_share),
                "validation_long_pnl": float(group.get("long_adjusted_pnl", pd.Series(dtype=float)).sum()),
                "validation_short_pnl": float(group.get("short_adjusted_pnl", pd.Series(dtype=float)).sum()),
                "validation_ev_over_realized": float(
                    group.get("ev_overestimate_vs_realized_mean", pd.Series(dtype=float)).mean()
                ),
                "validation_direction_session_pnl_min": float(
                    group.get("direction_session_adjusted_pnl_min", pd.Series(dtype=float)).min()
                ),
                "validation_combined_regime_pnl_min": float(
                    group.get("combined_regime_adjusted_pnl_min", pd.Series(dtype=float)).min()
                ),
                "validation_direction_combined_regime_pnl_min": float(
                    group.get("direction_combined_regime_adjusted_pnl_min", pd.Series(dtype=float)).min()
                ),
            }
        )

    summary = pd.DataFrame(rows)
    return summary.sort_values(
        ["validation_total", "validation_worst", "validation_trades"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def aggregate_multiwindow_validation(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate each family as a separate validation window."""
    window_summary = aggregate_validation(frame)
    grouped = window_summary.groupby(SWEEP_KEY_COLUMNS, dropna=False)
    rows: list[dict[str, object]] = []
    for keys, group in grouped:
        key_values = dict(zip(SWEEP_KEY_COLUMNS, keys, strict=True))
        trade_count = int(group["validation_trades"].sum())
        long_trades = int(group["validation_long_trades"].sum())
        short_trades = int(group["validation_short_trades"].sum())
        max_side_trade_share = (
            max(long_trades, short_trades) / trade_count if trade_count > 0 else 0.0
        )
        rows.append(
            {
                "family": "multi_window",
                **key_values,
                "validation_windows": int(group["family"].nunique()),
                "validation_positive_windows": int((group["validation_total"] > 0).sum()),
                "validation_active_windows": int((group["validation_trades"] > 0).sum()),
                "validation_worst_window": float(group["validation_total"].min()),
                "validation_best_window": float(group["validation_total"].max()),
                "months": int(group["months"].sum()),
                "validation_active_months": int(group["validation_active_months"].sum()),
                "validation_total": float(group["validation_total"].sum()),
                "validation_worst": float(group["validation_worst"].min()),
                "validation_trades": trade_count,
                "validation_min_monthly_trades": int(group["validation_min_monthly_trades"].min()),
                "validation_max_monthly_trades": int(group["validation_max_monthly_trades"].max()),
                "validation_min_window_trades": int(group["validation_trades"].min()),
                "validation_max_window_trades": int(group["validation_trades"].max()),
                "validation_max_dd": float(group["validation_max_dd"].max()),
                "validation_forced_exit_count": int(group["validation_forced_exit_count"].sum()),
                "validation_long_trades": long_trades,
                "validation_short_trades": short_trades,
                "validation_max_side_trade_share": float(max_side_trade_share),
                "validation_max_window_side_trade_share": float(
                    group["validation_max_side_trade_share"].max()
                ),
                "validation_long_pnl": float(group["validation_long_pnl"].sum()),
                "validation_short_pnl": float(group["validation_short_pnl"].sum()),
                "validation_ev_over_realized": float(
                    group["validation_ev_over_realized"].mean()
                ),
                "validation_direction_session_pnl_min": float(
                    group["validation_direction_session_pnl_min"].min()
                ),
                "validation_combined_regime_pnl_min": float(
                    group["validation_combined_regime_pnl_min"].min()
                ),
                "validation_direction_combined_regime_pnl_min": float(
                    group["validation_direction_combined_regime_pnl_min"].min()
                ),
                "validation_window_families": ",".join(sorted(group["family"].astype(str).unique())),
            }
        )

    summary = pd.DataFrame(rows)
    return summary.sort_values(
        ["validation_total", "validation_worst_window", "validation_worst"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def column_or_default(frame: pd.DataFrame, column: str, default: float) -> pd.Series:
    if column in frame.columns:
        return frame[column].fillna(default)
    return pd.Series(default, index=frame.index)


def filter_standard_candidates(
    summary: pd.DataFrame,
    *,
    min_positive_pnl: float,
    min_trades: int,
    min_active_months: int,
    min_worst_pnl: float,
    max_drawdown: float,
    min_windows: int = 0,
    min_positive_windows: int = 0,
    min_active_windows: int = 0,
    min_window_total: float = -float("inf"),
    min_window_trades: int = 0,
    min_monthly_trades: int = 0,
    max_monthly_trades: float = float("inf"),
    max_side_trade_share: float = float("inf"),
    min_direction_session_pnl: float = -float("inf"),
    min_combined_regime_pnl: float = -float("inf"),
    min_direction_combined_regime_pnl: float = -float("inf"),
) -> pd.DataFrame:
    return summary[
        (summary["validation_total"] > min_positive_pnl)
        & (summary["validation_trades"] >= min_trades)
        & (summary["validation_active_months"] >= min_active_months)
        & (summary["validation_worst"] >= min_worst_pnl)
        & (summary["validation_max_dd"] <= max_drawdown)
        & (column_or_default(summary, "validation_windows", min_windows) >= min_windows)
        & (
            column_or_default(summary, "validation_positive_windows", min_positive_windows)
            >= min_positive_windows
        )
        & (
            column_or_default(summary, "validation_active_windows", min_active_windows)
            >= min_active_windows
        )
        & (
            column_or_default(summary, "validation_worst_window", min_window_total)
            >= min_window_total
        )
        & (
            column_or_default(summary, "validation_min_window_trades", min_window_trades)
            >= min_window_trades
        )
        & (
            column_or_default(summary, "validation_min_monthly_trades", min_monthly_trades)
            >= min_monthly_trades
        )
        & (
            column_or_default(summary, "validation_max_monthly_trades", 0.0)
            <= max_monthly_trades
        )
        & (
            column_or_default(summary, "validation_max_side_trade_share", 0.0)
            <= max_side_trade_share
        )
        & (
            column_or_default(
                summary,
                "validation_direction_session_pnl_min",
                min_direction_session_pnl,
            )
            >= min_direction_session_pnl
        )
        & (
            column_or_default(
                summary,
                "validation_combined_regime_pnl_min",
                min_combined_regime_pnl,
            )
            >= min_combined_regime_pnl
        )
        & (
            column_or_default(
                summary,
                "validation_direction_combined_regime_pnl_min",
                min_direction_combined_regime_pnl,
            )
            >= min_direction_combined_regime_pnl
        )
    ].copy()


def select_standard_policy(
    summary: pd.DataFrame,
    *,
    min_positive_pnl: float,
    min_trades: int,
    min_active_months: int,
    min_worst_pnl: float,
    max_drawdown: float,
    min_windows: int = 0,
    min_positive_windows: int = 0,
    min_active_windows: int = 0,
    min_window_total: float = -float("inf"),
    min_window_trades: int = 0,
    min_monthly_trades: int = 0,
    max_monthly_trades: float = float("inf"),
    max_side_trade_share: float = float("inf"),
    min_direction_session_pnl: float = -float("inf"),
    min_combined_regime_pnl: float = -float("inf"),
    min_direction_combined_regime_pnl: float = -float("inf"),
) -> dict[str, object]:
    eligible = filter_standard_candidates(
        summary,
        min_positive_pnl=min_positive_pnl,
        min_trades=min_trades,
        min_active_months=min_active_months,
        min_worst_pnl=min_worst_pnl,
        max_drawdown=max_drawdown,
        min_windows=min_windows,
        min_positive_windows=min_positive_windows,
        min_active_windows=min_active_windows,
        min_window_total=min_window_total,
        min_window_trades=min_window_trades,
        min_monthly_trades=min_monthly_trades,
        max_monthly_trades=max_monthly_trades,
        max_side_trade_share=max_side_trade_share,
        min_direction_session_pnl=min_direction_session_pnl,
        min_combined_regime_pnl=min_combined_regime_pnl,
        min_direction_combined_regime_pnl=min_direction_combined_regime_pnl,
    )
    if eligible.empty:
        best_total = float(summary["validation_total"].max()) if not summary.empty else 0.0
        return {
            "selector": "standard_no_trade_first",
            "selected": "no_trade",
            "reason": "no validation row exceeded NoTrade threshold and robustness gates",
            "min_positive_pnl": min_positive_pnl,
            "min_trades": min_trades,
            "min_active_months": min_active_months,
            "min_worst_pnl": min_worst_pnl,
            "max_drawdown": max_drawdown,
            "min_windows": min_windows,
            "min_positive_windows": min_positive_windows,
            "min_active_windows": min_active_windows,
            "min_window_total": min_window_total,
            "min_window_trades": min_window_trades,
            "min_monthly_trades": min_monthly_trades,
            "max_monthly_trades": max_monthly_trades,
            "max_side_trade_share": max_side_trade_share,
            "min_direction_session_pnl": min_direction_session_pnl,
            "min_combined_regime_pnl": min_combined_regime_pnl,
            "min_direction_combined_regime_pnl": min_direction_combined_regime_pnl,
            "best_validation_total": best_total,
        }
    selected = eligible.sort_values(
        ["validation_total", "validation_worst", "validation_max_dd", "validation_trades"],
        ascending=[False, False, True, True],
    ).iloc[0]
    return {
        "selector": "standard_no_trade_first",
        "selected": "policy",
        "reason": "validation row exceeded NoTrade threshold and robustness gates",
        **selected.to_dict(),
    }


def select_near_notrade_diagnostic(
    summary: pd.DataFrame,
    *,
    near_notrade_tolerance: float,
    max_trades: int,
) -> dict[str, object]:
    candidates = summary[
        (summary["validation_total"] >= -near_notrade_tolerance)
        & (summary["validation_total"] <= near_notrade_tolerance)
        & (summary["validation_trades"] <= max_trades)
    ].copy()
    if candidates.empty:
        return {
            "selector": "diagnostic_near_notrade_conservative",
            "selected": "none",
            "reason": "no low-frequency row was close enough to NoTrade",
            "near_notrade_tolerance": near_notrade_tolerance,
            "max_trades": max_trades,
        }
    selected = candidates.sort_values(
        [
            "entry_threshold",
            "short_entry_threshold_offset",
            "validation_trades",
            "validation_total",
        ],
        ascending=[False, False, True, False],
    ).iloc[0]
    return {
        "selector": "diagnostic_near_notrade_conservative",
        "selected": "policy",
        "reason": "low-frequency row was close to NoTrade; diagnostic only",
        "near_notrade_tolerance": near_notrade_tolerance,
        "max_trades": max_trades,
        **selected.to_dict(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--family-sweeps",
        action="append",
        required=True,
        help="family=path1,path2; repeatable",
    )
    parser.add_argument("--min-positive-pnl", type=float, default=0.0)
    parser.add_argument("--min-trades", type=int, default=1)
    parser.add_argument("--min-active-months", type=int, default=0)
    parser.add_argument("--min-worst-pnl", type=float, default=-float("inf"))
    parser.add_argument("--max-drawdown", type=float, default=float("inf"))
    parser.add_argument(
        "--multi-window",
        action="store_true",
        help="treat each family as one validation window and select across windows",
    )
    parser.add_argument("--min-windows", type=int, default=0)
    parser.add_argument("--min-positive-windows", type=int, default=0)
    parser.add_argument("--min-active-windows", type=int, default=0)
    parser.add_argument("--min-window-total", type=float, default=-float("inf"))
    parser.add_argument("--min-window-trades", type=int, default=0)
    parser.add_argument("--min-monthly-trades", type=int, default=0)
    parser.add_argument("--max-monthly-trades", type=float, default=float("inf"))
    parser.add_argument("--max-side-trade-share", type=float, default=float("inf"))
    parser.add_argument("--min-direction-session-pnl", type=float, default=-float("inf"))
    parser.add_argument("--min-combined-regime-pnl", type=float, default=-float("inf"))
    parser.add_argument(
        "--min-direction-combined-regime-pnl",
        type=float,
        default=-float("inf"),
    )
    parser.add_argument("--near-notrade-tolerance", type=float, default=2.0)
    parser.add_argument("--diagnostic-max-trades", type=int, default=10)
    parser.add_argument("--label", default="entry_ev_admission_selection")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    families = parse_family_sweeps(args.family_sweeps)
    frame = read_family_sweeps(families)
    window_summary = aggregate_validation(frame) if args.multi_window else None
    summary = (
        aggregate_multiwindow_validation(frame)
        if args.multi_window
        else aggregate_validation(frame)
    )
    standard = select_standard_policy(
        summary,
        min_positive_pnl=args.min_positive_pnl,
        min_trades=args.min_trades,
        min_active_months=args.min_active_months,
        min_worst_pnl=args.min_worst_pnl,
        max_drawdown=args.max_drawdown,
        min_windows=args.min_windows,
        min_positive_windows=args.min_positive_windows,
        min_active_windows=args.min_active_windows,
        min_window_total=args.min_window_total,
        min_window_trades=args.min_window_trades,
        min_monthly_trades=args.min_monthly_trades,
        max_monthly_trades=args.max_monthly_trades,
        max_side_trade_share=args.max_side_trade_share,
        min_direction_session_pnl=args.min_direction_session_pnl,
        min_combined_regime_pnl=args.min_combined_regime_pnl,
        min_direction_combined_regime_pnl=args.min_direction_combined_regime_pnl,
    )
    diagnostic = select_near_notrade_diagnostic(
        summary,
        near_notrade_tolerance=args.near_notrade_tolerance,
        max_trades=args.diagnostic_max_trades,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    summary.to_csv(run_dir / "validation_summary.csv", index=False)
    if window_summary is not None:
        window_summary.to_csv(run_dir / "window_validation_summary.csv", index=False)
    pd.DataFrame([standard, diagnostic]).to_csv(run_dir / "selections.csv", index=False)
    manifest = {
        "mode": "entry_ev_admission_selection",
        "multi_window": args.multi_window,
        "families": {family: [str(path) for path in paths] for family, paths in families.items()},
        "min_positive_pnl": args.min_positive_pnl,
        "min_trades": args.min_trades,
        "min_active_months": args.min_active_months,
        "min_worst_pnl": args.min_worst_pnl,
        "max_drawdown": args.max_drawdown,
        "min_windows": args.min_windows,
        "min_positive_windows": args.min_positive_windows,
        "min_active_windows": args.min_active_windows,
        "min_window_total": args.min_window_total,
        "min_window_trades": args.min_window_trades,
        "min_monthly_trades": args.min_monthly_trades,
        "max_monthly_trades": args.max_monthly_trades,
        "max_side_trade_share": args.max_side_trade_share,
        "min_direction_session_pnl": args.min_direction_session_pnl,
        "min_combined_regime_pnl": args.min_combined_regime_pnl,
        "min_direction_combined_regime_pnl": args.min_direction_combined_regime_pnl,
        "near_notrade_tolerance": args.near_notrade_tolerance,
        "diagnostic_max_trades": args.diagnostic_max_trades,
        "standard_selection": standard,
        "diagnostic_selection": diagnostic,
    }
    (run_dir / "selection.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print(f"artifacts: {run_dir}")
    print(pd.DataFrame([standard, diagnostic]).to_string(index=False))
    print(summary.head(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
