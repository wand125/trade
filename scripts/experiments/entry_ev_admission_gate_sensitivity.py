#!/usr/bin/env python3
"""Evaluate entry-EV admission gate sensitivity from existing selector summaries."""

from __future__ import annotations

import argparse
import json
import sys
from itertools import product
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

from entry_ev_admission_selection import (  # noqa: E402
    filter_standard_candidates,
    local_json_default,
    select_standard_policy,
)
from trade_data.backtest import SWEEP_KEY_COLUMNS, make_run_dir  # noqa: E402


GATE_COLUMNS = [
    "min_window_trades",
    "max_side_trade_share",
    "min_direction_session_pnl",
    "min_combined_regime_pnl",
    "min_direction_combined_regime_pnl",
]

SELECTED_SUMMARY_COLUMNS = [
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
    "validation_worst_window",
    "validation_best_window",
    "months",
    "validation_active_months",
    "validation_total",
    "validation_worst",
    "validation_trades",
    "validation_min_monthly_trades",
    "validation_max_monthly_trades",
    "validation_min_window_trades",
    "validation_max_window_trades",
    "validation_max_dd",
    "validation_long_trades",
    "validation_short_trades",
    "validation_max_side_trade_share",
    "validation_max_window_side_trade_share",
    "validation_long_pnl",
    "validation_short_pnl",
    "validation_direction_session_pnl_min",
    "validation_combined_regime_pnl_min",
    "validation_direction_combined_regime_pnl_min",
]


def parse_float_token(value: str) -> float:
    token = value.strip().lower()
    if token in {"inf", "+inf", "infinity", "+infinity"}:
        return float("inf")
    if token in {"-inf", "-infinity"}:
        return -float("inf")
    return float(token)


def parse_float_list(value: str) -> list[float]:
    values = [parse_float_token(part) for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one numeric value is required")
    return values


def parse_int_list(value: str) -> list[int]:
    values: list[int] = []
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        number = float(token)
        if not number.is_integer():
            raise argparse.ArgumentTypeError(f"{token} is not an integer")
        values.append(int(number))
    if not values:
        raise argparse.ArgumentTypeError("at least one integer value is required")
    return values


def iter_gate_grid(args: argparse.Namespace) -> list[dict[str, float | int]]:
    gates: list[dict[str, float | int]] = []
    for values in product(
        args.min_window_trades_values,
        args.max_side_trade_share_values,
        args.min_direction_session_pnl_values,
        args.min_combined_regime_pnl_values,
        args.min_direction_combined_regime_pnl_values,
    ):
        gates.append(dict(zip(GATE_COLUMNS, values, strict=True)))
    return gates


def fixed_metrics_for_selection(
    selected: dict[str, object],
    fixed_summary: pd.DataFrame | None,
) -> dict[str, object]:
    if fixed_summary is None or selected.get("selected") != "policy":
        return {"fixed_match_count": 0, "fixed_join_columns": ""}

    join_columns = [
        column
        for column in SWEEP_KEY_COLUMNS
        if column in selected and column in fixed_summary.columns
    ]
    if not join_columns:
        return {"fixed_match_count": 0, "fixed_join_columns": ""}

    selected_key = pd.DataFrame([{column: selected[column] for column in join_columns}])
    matches = fixed_summary.merge(selected_key, on=join_columns, how="inner")
    metrics: dict[str, object] = {
        "fixed_match_count": int(len(matches)),
        "fixed_join_columns": ",".join(join_columns),
    }
    if matches.empty:
        return metrics

    sort_columns: list[str] = []
    ascending: list[bool] = []
    for column, order in (
        ("total_pnl", False),
        ("worst_pnl", False),
        ("max_dd", True),
        ("trades", True),
    ):
        if column in matches.columns:
            sort_columns.append(column)
            ascending.append(order)
    fixed_row = (
        matches.sort_values(sort_columns, ascending=ascending).iloc[0]
        if sort_columns
        else matches.iloc[0]
    )
    for column, value in fixed_row.items():
        if column not in join_columns:
            metrics[f"fixed_{column}"] = value
    return metrics


def select_with_gate(
    validation_summary: pd.DataFrame,
    fixed_summary: pd.DataFrame | None,
    gate_id: int,
    base_gates: dict[str, float | int],
    gate: dict[str, float | int],
) -> tuple[dict[str, object], dict[str, object] | None]:
    selector_args = {**base_gates, **gate}
    eligible = filter_standard_candidates(validation_summary, **selector_args)
    selected = select_standard_policy(validation_summary, **selector_args)
    fixed_metrics = fixed_metrics_for_selection(selected, fixed_summary)

    row: dict[str, object] = {
        "gate_id": gate_id,
        **selector_args,
        "eligible_count": int(len(eligible)),
        "selected": selected.get("selected"),
        "reason": selected.get("reason"),
    }
    if "best_validation_total" in selected:
        row["best_validation_total"] = selected["best_validation_total"]
    for column in SELECTED_SUMMARY_COLUMNS:
        if column in selected:
            row[f"selected_{column}"] = selected[column]
    row.update(fixed_metrics)

    detail_row: dict[str, object] | None = None
    if selected.get("selected") == "policy":
        detail_row = {
            "gate_id": gate_id,
            **selector_args,
            "eligible_count": int(len(eligible)),
            **selected,
            **fixed_metrics,
        }
    return row, detail_row


def evaluate_gate_grid(
    validation_summary: pd.DataFrame,
    fixed_summary: pd.DataFrame | None,
    base_gates: dict[str, float | int],
    gates: list[dict[str, float | int]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    details: list[dict[str, object]] = []
    for gate_id, gate in enumerate(gates, start=1):
        row, detail = select_with_gate(
            validation_summary,
            fixed_summary,
            gate_id,
            base_gates,
            gate,
        )
        rows.append(row)
        if detail is not None:
            details.append(detail)
    return pd.DataFrame(rows), pd.DataFrame(details)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-summary", type=Path, required=True)
    parser.add_argument("--fixed-test-summary", type=Path)
    parser.add_argument("--min-positive-pnl", type=float, default=0.0)
    parser.add_argument("--min-trades", type=int, default=1)
    parser.add_argument("--min-active-months", type=int, default=0)
    parser.add_argument("--min-worst-pnl", type=float, default=-float("inf"))
    parser.add_argument("--max-drawdown", type=float, default=float("inf"))
    parser.add_argument("--min-windows", type=int, default=0)
    parser.add_argument("--min-positive-windows", type=int, default=0)
    parser.add_argument("--min-active-windows", type=int, default=0)
    parser.add_argument("--min-window-total", type=float, default=-float("inf"))
    parser.add_argument("--min-monthly-trades", type=int, default=0)
    parser.add_argument("--max-monthly-trades", type=float, default=float("inf"))
    parser.add_argument(
        "--min-window-trades-values",
        type=parse_int_list,
        default=[0],
    )
    parser.add_argument(
        "--max-side-trade-share-values",
        type=parse_float_list,
        default=[float("inf")],
    )
    parser.add_argument(
        "--min-direction-session-pnl-values",
        type=parse_float_list,
        default=[-float("inf")],
    )
    parser.add_argument(
        "--min-combined-regime-pnl-values",
        type=parse_float_list,
        default=[-float("inf")],
    )
    parser.add_argument(
        "--min-direction-combined-regime-pnl-values",
        type=parse_float_list,
        default=[-float("inf")],
    )
    parser.add_argument("--label", default="entry_ev_admission_gate_sensitivity")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    return parser


def local_manifest_default(value: Any) -> Any:
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
    base_gates = {
        "min_positive_pnl": args.min_positive_pnl,
        "min_trades": args.min_trades,
        "min_active_months": args.min_active_months,
        "min_worst_pnl": args.min_worst_pnl,
        "max_drawdown": args.max_drawdown,
        "min_windows": args.min_windows,
        "min_positive_windows": args.min_positive_windows,
        "min_active_windows": args.min_active_windows,
        "min_window_total": args.min_window_total,
        "min_monthly_trades": args.min_monthly_trades,
        "max_monthly_trades": args.max_monthly_trades,
    }
    gates = iter_gate_grid(args)
    sensitivity, details = evaluate_gate_grid(
        validation_summary,
        fixed_summary,
        base_gates,
        gates,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    sensitivity.to_csv(run_dir / "gate_sensitivity.csv", index=False)
    details.to_csv(run_dir / "selected_policy_details.csv", index=False)
    manifest = {
        "mode": "entry_ev_admission_gate_sensitivity",
        "validation_summary": str(args.validation_summary),
        "fixed_test_summary": str(args.fixed_test_summary)
        if args.fixed_test_summary is not None
        else None,
        "base_gates": base_gates,
        "grid": {
            "min_window_trades_values": args.min_window_trades_values,
            "max_side_trade_share_values": args.max_side_trade_share_values,
            "min_direction_session_pnl_values": args.min_direction_session_pnl_values,
            "min_combined_regime_pnl_values": args.min_combined_regime_pnl_values,
            "min_direction_combined_regime_pnl_values": args.min_direction_combined_regime_pnl_values,
        },
        "gate_count": len(gates),
        "policy_selection_count": int((sensitivity["selected"] == "policy").sum()),
        "no_trade_count": int((sensitivity["selected"] == "no_trade").sum()),
    }
    (run_dir / "selection.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=local_manifest_default)
        + "\n",
        encoding="utf-8",
    )

    print(f"artifacts: {run_dir}")
    print_columns = [
        "gate_id",
        *GATE_COLUMNS,
        "eligible_count",
        "selected",
        "selected_entry_threshold",
        "selected_short_entry_threshold_offset",
        "selected_min_entry_rank",
        "selected_validation_total",
        "fixed_total_pnl",
    ]
    print(sensitivity.reindex(columns=print_columns).head(25).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
