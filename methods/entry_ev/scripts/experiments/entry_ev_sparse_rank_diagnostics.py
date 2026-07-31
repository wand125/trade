#!/usr/bin/env python3
"""Diagnose sparse high-rank entry-EV candidates without selecting on fixed PnL."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
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

from entry_ev_admission_selection import column_or_default, local_json_default  # noqa: E402
from trade_data.backtest import SWEEP_KEY_COLUMNS, make_run_dir  # noqa: E402


DIAGNOSTIC_COLUMNS = [
    "policy",
    "entry_threshold",
    "long_entry_threshold_offset",
    "short_entry_threshold_offset",
    "exit_threshold",
    "side_margin",
    "risk_penalty",
    "min_entry_rank",
    "validation_windows",
    "validation_positive_windows",
    "validation_active_windows",
    "validation_total",
    "validation_worst",
    "validation_worst_window",
    "validation_trades",
    "validation_active_months",
    "validation_min_window_trades",
    "validation_max_side_trade_share",
    "validation_direction_session_pnl_min",
    "validation_combined_regime_pnl_min",
    "validation_direction_combined_regime_pnl_min",
    "promotion_eligible_by_validation",
    "validation_blockers",
    "fixed_total_pnl",
    "fixed_worst_pnl",
    "fixed_trades",
    "fixed_positive_audit",
]


def common_sweep_key_columns(left: pd.DataFrame, right: pd.DataFrame) -> list[str]:
    return [
        column
        for column in SWEEP_KEY_COLUMNS
        if column in left.columns and column in right.columns
    ]


def attach_fixed_metrics(
    validation_summary: pd.DataFrame,
    fixed_summary: pd.DataFrame | None,
) -> tuple[pd.DataFrame, list[str]]:
    if fixed_summary is None:
        frame = validation_summary.copy()
        frame["fixed_match_count"] = 0
        return frame, []

    join_columns = common_sweep_key_columns(validation_summary, fixed_summary)
    if not join_columns:
        frame = validation_summary.copy()
        frame["fixed_match_count"] = 0
        return frame, []

    fixed_prefixed = fixed_summary.copy()
    metric_columns = [column for column in fixed_prefixed.columns if column not in join_columns]
    fixed_prefixed = fixed_prefixed.rename(
        columns={column: f"fixed_{column}" for column in metric_columns}
    )
    fixed_prefixed["fixed_match_count"] = 1
    merged = validation_summary.merge(fixed_prefixed, on=join_columns, how="left")
    merged["fixed_match_count"] = merged["fixed_match_count"].fillna(0).astype(int)
    return merged, join_columns


def validation_blockers(row: pd.Series, gates: dict[str, float | int]) -> list[str]:
    blockers: list[str] = []
    if float(row["validation_total"]) <= float(gates["min_positive_pnl"]):
        blockers.append("validation_total_not_positive")
    if int(row["validation_trades"]) < int(gates["min_trades"]):
        blockers.append("validation_trades_low")
    if int(row["validation_active_months"]) < int(gates["min_active_months"]):
        blockers.append("validation_active_months_low")
    if float(row["validation_worst"]) < float(gates["min_worst_pnl"]):
        blockers.append("validation_worst_below_floor")
    if float(row.get("validation_worst_window", gates["min_window_total"])) < float(
        gates["min_window_total"]
    ):
        blockers.append("validation_worst_window_below_floor")
    if int(row.get("validation_min_window_trades", gates["min_window_trades"])) < int(
        gates["min_window_trades"]
    ):
        blockers.append("validation_window_trades_low")
    if float(row.get("validation_max_side_trade_share", 0.0)) > float(
        gates["max_side_trade_share"]
    ):
        blockers.append("validation_side_share_high")
    if float(row.get("validation_direction_session_pnl_min", gates["min_direction_session_pnl"])) < float(
        gates["min_direction_session_pnl"]
    ):
        blockers.append("direction_session_floor_breach")
    if float(row.get("validation_combined_regime_pnl_min", gates["min_combined_regime_pnl"])) < float(
        gates["min_combined_regime_pnl"]
    ):
        blockers.append("combined_regime_floor_breach")
    if float(
        row.get(
            "validation_direction_combined_regime_pnl_min",
            gates["min_direction_combined_regime_pnl"],
        )
    ) < float(gates["min_direction_combined_regime_pnl"]):
        blockers.append("direction_combined_regime_floor_breach")
    return blockers


def add_validation_diagnostics(
    frame: pd.DataFrame,
    gates: dict[str, float | int],
) -> pd.DataFrame:
    result = frame.copy()
    defaults = {
        "validation_worst_window": gates["min_window_total"],
        "validation_min_window_trades": gates["min_window_trades"],
        "validation_max_side_trade_share": 0.0,
        "validation_direction_session_pnl_min": gates["min_direction_session_pnl"],
        "validation_combined_regime_pnl_min": gates["min_combined_regime_pnl"],
        "validation_direction_combined_regime_pnl_min": gates[
            "min_direction_combined_regime_pnl"
        ],
    }
    for column, default in defaults.items():
        result[column] = column_or_default(result, column, float(default))

    blocker_lists = [validation_blockers(row, gates) for _, row in result.iterrows()]
    result["validation_blockers"] = [
        ";".join(blockers) if blockers else "" for blockers in blocker_lists
    ]
    result["promotion_eligible_by_validation"] = [not blockers for blockers in blocker_lists]
    result["fixed_positive_audit"] = result.get(
        "fixed_total_pnl",
        pd.Series(np.nan, index=result.index),
    ).gt(0)
    return result


def build_blocker_summary(frame: pd.DataFrame) -> pd.DataFrame:
    counter: Counter[str] = Counter()
    fixed_positive_counter: Counter[str] = Counter()
    for _, row in frame.iterrows():
        blockers = [part for part in str(row["validation_blockers"]).split(";") if part]
        for blocker in blockers:
            counter[blocker] += 1
            if bool(row.get("fixed_positive_audit", False)):
                fixed_positive_counter[blocker] += 1
    names = sorted(set(counter) | set(fixed_positive_counter))
    return pd.DataFrame(
        [
            {
                "blocker": name,
                "candidate_count": counter[name],
                "fixed_positive_candidate_count": fixed_positive_counter[name],
            }
            for name in names
        ]
    ).sort_values(
        ["fixed_positive_candidate_count", "candidate_count", "blocker"],
        ascending=[False, False, True],
    )


def build_rank_summary(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby("min_entry_rank", dropna=False)
    rows: list[dict[str, object]] = []
    for rank, group in grouped:
        rows.append(
            {
                "min_entry_rank": rank,
                "candidate_count": int(len(group)),
                "validation_positive_count": int((group["validation_total"] > 0).sum()),
                "promotion_eligible_count": int(
                    group["promotion_eligible_by_validation"].sum()
                ),
                "fixed_positive_count": int(group["fixed_positive_audit"].sum()),
                "validation_total_max": float(group["validation_total"].max()),
                "validation_total_mean": float(group["validation_total"].mean()),
                "validation_min_window_trades_min": int(
                    group["validation_min_window_trades"].min()
                ),
                "validation_max_side_share_max": float(
                    group["validation_max_side_trade_share"].max()
                ),
                "fixed_total_pnl_max": float(group["fixed_total_pnl"].max())
                if "fixed_total_pnl" in group
                else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("min_entry_rank").reset_index(drop=True)


def build_window_details(
    window_summary: pd.DataFrame | None,
    diagnostics: pd.DataFrame,
) -> pd.DataFrame:
    if window_summary is None:
        return pd.DataFrame()
    join_columns = common_sweep_key_columns(window_summary, diagnostics)
    if not join_columns:
        return pd.DataFrame()
    focus = diagnostics[
        diagnostics["fixed_positive_audit"] | diagnostics["promotion_eligible_by_validation"]
    ][join_columns].drop_duplicates()
    if focus.empty:
        return pd.DataFrame()
    return window_summary.merge(focus, on=join_columns, how="inner").sort_values(
        [*join_columns, "family"]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-summary", type=Path, required=True)
    parser.add_argument("--window-validation-summary", type=Path)
    parser.add_argument("--fixed-test-summary", type=Path)
    parser.add_argument("--min-positive-pnl", type=float, default=0.0)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--min-active-months", type=int, default=4)
    parser.add_argument("--min-worst-pnl", type=float, default=0.0)
    parser.add_argument("--min-window-total", type=float, default=0.0)
    parser.add_argument("--min-window-trades", type=int, default=1)
    parser.add_argument("--max-side-trade-share", type=float, default=0.95)
    parser.add_argument("--min-direction-session-pnl", type=float, default=-float("inf"))
    parser.add_argument("--min-combined-regime-pnl", type=float, default=-float("inf"))
    parser.add_argument(
        "--min-direction-combined-regime-pnl",
        type=float,
        default=-float("inf"),
    )
    parser.add_argument("--label", default="entry_ev_sparse_rank_diagnostics")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    return parser


def manifest_default(value: Any) -> Any:
    try:
        return local_json_default(value)
    except TypeError:
        pass
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"cannot serialize {type(value).__name__}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validation_summary = pd.read_csv(args.validation_summary)
    fixed_summary = (
        pd.read_csv(args.fixed_test_summary)
        if args.fixed_test_summary is not None
        else None
    )
    window_summary = (
        pd.read_csv(args.window_validation_summary)
        if args.window_validation_summary is not None
        else None
    )
    gates = {
        "min_positive_pnl": args.min_positive_pnl,
        "min_trades": args.min_trades,
        "min_active_months": args.min_active_months,
        "min_worst_pnl": args.min_worst_pnl,
        "min_window_total": args.min_window_total,
        "min_window_trades": args.min_window_trades,
        "max_side_trade_share": args.max_side_trade_share,
        "min_direction_session_pnl": args.min_direction_session_pnl,
        "min_combined_regime_pnl": args.min_combined_regime_pnl,
        "min_direction_combined_regime_pnl": args.min_direction_combined_regime_pnl,
    }
    merged, fixed_join_columns = attach_fixed_metrics(validation_summary, fixed_summary)
    diagnostics = add_validation_diagnostics(merged, gates)
    rank_summary = build_rank_summary(diagnostics)
    blocker_summary = build_blocker_summary(diagnostics)
    window_details = build_window_details(window_summary, diagnostics)

    run_dir = make_run_dir(args.output_dir, args.label)
    diagnostics.reindex(columns=[c for c in DIAGNOSTIC_COLUMNS if c in diagnostics.columns]).to_csv(
        run_dir / "candidate_diagnostics.csv",
        index=False,
    )
    rank_summary.to_csv(run_dir / "rank_summary.csv", index=False)
    blocker_summary.to_csv(run_dir / "blocker_summary.csv", index=False)
    if not window_details.empty:
        window_details.to_csv(run_dir / "window_details.csv", index=False)
    manifest = {
        "mode": "entry_ev_sparse_rank_diagnostics",
        "validation_summary": str(args.validation_summary),
        "window_validation_summary": str(args.window_validation_summary)
        if args.window_validation_summary is not None
        else None,
        "fixed_test_summary": str(args.fixed_test_summary)
        if args.fixed_test_summary is not None
        else None,
        "fixed_join_columns": fixed_join_columns,
        "validation_gates": gates,
        "candidate_count": int(len(diagnostics)),
        "promotion_eligible_count": int(
            diagnostics["promotion_eligible_by_validation"].sum()
        ),
        "fixed_positive_audit_count": int(diagnostics["fixed_positive_audit"].sum()),
    }
    (run_dir / "diagnostics.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=manifest_default) + "\n",
        encoding="utf-8",
    )

    print(f"artifacts: {run_dir}")
    print(rank_summary.to_string(index=False))
    fixed_positive = diagnostics[diagnostics["fixed_positive_audit"]]
    if not fixed_positive.empty:
        print(
            fixed_positive.reindex(columns=[c for c in DIAGNOSTIC_COLUMNS if c in fixed_positive.columns])
            .to_string(index=False)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
