#!/usr/bin/env python3
"""Compare two entry-EV trade sets by added, removed, and changed trades."""

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


DEFAULT_KEY_COLUMNS = (
    "role,family,candidate,direction,entry_decision_timestamp"
)
DEFAULT_RULES = "none,long_range_normal_ny_fixed60_pred_gt0,holdext_long_range_normal_ny"
DEFAULT_CONTEXT_COLUMNS = (
    "role,family,month,direction,combined_regime,session_regime,entry_block_rule"
)


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


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        return values.fillna(float(default)).astype(float).ne(0.0)
    return values.astype(str).str.lower().str.strip().isin({"true", "1", "yes", "y"})


def text_series(frame: pd.DataFrame, column: str, default: str = "missing") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="string")
    return (
        frame[column]
        .astype("string")
        .fillna(default)
        .str.strip()
        .replace({"": default, "nan": default, "None": default})
    )


def resolve_trade_file(path: Path) -> Path:
    if path.is_dir():
        return path / "entry_block_overlay_trades.csv"
    return path


def read_trade_set(
    path: Path,
    *,
    label: str,
    key_columns: list[str],
    entry_block_rules: list[str],
    selector_variant_contains: str,
) -> pd.DataFrame:
    file_path = resolve_trade_file(path)
    frame = pd.read_csv(file_path)
    missing = sorted(set(key_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{file_path} missing key columns: {', '.join(missing)}")
    if "adjusted_pnl" not in frame.columns:
        raise ValueError(f"{file_path} missing adjusted_pnl")
    output = frame.copy()
    output["set_label"] = label
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl", default=0.0)
    output["entry_blocked"] = bool_series(output, "entry_blocked", default=False)
    if "entry_block_rule" in output.columns:
        output["entry_block_rule"] = text_series(output, "entry_block_rule")
    else:
        output["entry_block_rule"] = "none"
    if "selector_variant" in output.columns:
        output["selector_variant"] = text_series(output, "selector_variant")
    else:
        output["selector_variant"] = "missing"
    if selector_variant_contains:
        output = output[
            output["selector_variant"].str.contains(selector_variant_contains, regex=False)
        ].copy()
    if entry_block_rules:
        output = output[output["entry_block_rule"].isin(entry_block_rules)].copy()
    for column in output.columns:
        if column.endswith("timestamp") or column.endswith("_timestamp"):
            output[column] = pd.to_datetime(output[column], utc=True, errors="coerce")
    for column in [
        "role",
        "family",
        "candidate",
        "direction",
        "month",
        "combined_regime",
        "session_regime",
        "entry_block_rule",
        "selector_variant",
    ]:
        if column in output.columns:
            output[column] = text_series(output, column)
    if "month" in output.columns:
        output["month"] = output["month"].astype(str).str.slice(0, 7)
    if "direction" in output.columns:
        output["direction"] = output["direction"].astype(str).str.lower()
    duplicated = output.duplicated(["entry_block_rule", *key_columns], keep=False)
    if duplicated.any():
        examples = output.loc[
            duplicated,
            ["entry_block_rule", *key_columns],
        ].drop_duplicates().head(5)
        raise ValueError(
            f"{file_path} has duplicate keys: {examples.to_dict(orient='records')}"
        )
    return output.reset_index(drop=True)


def prefixed_columns(frame: pd.DataFrame, prefix: str, key_columns: list[str]) -> pd.DataFrame:
    keep = frame.copy()
    rename = {
        column: f"{prefix}_{column}"
        for column in keep.columns
        if column not in ["entry_block_rule", *key_columns]
    }
    return keep.rename(columns=rename)


def first_available(row: pd.Series, names: list[str], default: Any = np.nan) -> Any:
    for name in names:
        if name in row and pd.notna(row[name]):
            return row[name]
    return default


def compare_rule_trade_sets(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    key_columns: list[str],
    context_columns: list[str],
    rule: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    left_rule = left[left["entry_block_rule"].eq(rule)].copy()
    right_rule = right[right["entry_block_rule"].eq(rule)].copy()
    left_kept = left_rule[~left_rule["entry_blocked"]].copy()
    right_kept = right_rule[~right_rule["entry_blocked"]].copy()
    joined = prefixed_columns(left_kept, "left", key_columns).merge(
        prefixed_columns(right_kept, "right", key_columns),
        how="outer",
        on=["entry_block_rule", *key_columns],
        indicator=True,
    )

    rows: list[dict[str, Any]] = []
    for _, row in joined.iterrows():
        merge_status = str(row["_merge"])
        left_pnl = (
            float(row.get("left_adjusted_pnl", 0.0) or 0.0)
            if merge_status != "right_only"
            else 0.0
        )
        right_pnl = (
            float(row.get("right_adjusted_pnl", 0.0) or 0.0)
            if merge_status != "left_only"
            else 0.0
        )
        if merge_status == "left_only":
            status = "removed"
        elif merge_status == "right_only":
            status = "added"
        elif abs(right_pnl - left_pnl) > 1e-9:
            status = "common_changed"
        else:
            status = "common_same"
        output: dict[str, Any] = {
            "entry_block_rule": rule,
            "change_status": status,
            "left_adjusted_pnl": left_pnl,
            "right_adjusted_pnl": right_pnl,
            "delta_adjusted_pnl": right_pnl - left_pnl,
        }
        for column in key_columns:
            output[column] = row[column]
        for column in context_columns:
            if column in output:
                continue
            output[column] = first_available(
                row,
                [f"right_{column}", f"left_{column}", column],
                default="missing",
            )
        for column in [
            "entry_timestamp",
            "exit_timestamp",
            "adjusted_pnl",
            "base_adjusted_pnl",
            "selected_loss_first_prob",
            "pred_side_confidence_gap",
            "pred_taken_entry_local_rank",
            "pred_taken_ev",
            "selected_fixed_60m_pred_pnl",
            "selected_fixed_60m_actual_pnl",
            "hold_extension_applied",
            "hold_extension_delta_vs_base",
        ]:
            output[f"left_{column}"] = row.get(f"left_{column}", np.nan)
            output[f"right_{column}"] = row.get(f"right_{column}", np.nan)
        rows.append(output)

    delta_rows = pd.DataFrame(rows)
    left_blocked = left_rule[left_rule["entry_blocked"]].copy()
    right_blocked = right_rule[right_rule["entry_blocked"]].copy()
    summary = {
        "entry_block_rule": rule,
        "left_input_count": int(len(left_rule)),
        "right_input_count": int(len(right_rule)),
        "left_kept_count": int(len(left_kept)),
        "right_kept_count": int(len(right_kept)),
        "left_kept_pnl": float(left_kept["adjusted_pnl"].sum()),
        "right_kept_pnl": float(right_kept["adjusted_pnl"].sum()),
        "delta_pnl": float(
            right_kept["adjusted_pnl"].sum() - left_kept["adjusted_pnl"].sum()
        ),
        "left_blocked_count": int(len(left_blocked)),
        "right_blocked_count": int(len(right_blocked)),
        "left_blocked_pnl": float(left_blocked["adjusted_pnl"].sum()),
        "right_blocked_pnl": float(right_blocked["adjusted_pnl"].sum()),
    }
    for status in ["added", "removed", "common_changed", "common_same"]:
        status_rows = delta_rows[delta_rows["change_status"].eq(status)]
        summary[f"{status}_count"] = int(len(status_rows))
        summary[f"{status}_delta_pnl"] = float(status_rows["delta_adjusted_pnl"].sum())
    return delta_rows, summary


def compare_blocked_sets(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    key_columns: list[str],
    context_columns: list[str],
    rule: str,
) -> pd.DataFrame:
    left_blocked = left[
        left["entry_block_rule"].eq(rule) & left["entry_blocked"]
    ].copy()
    right_blocked = right[
        right["entry_block_rule"].eq(rule) & right["entry_blocked"]
    ].copy()
    joined = prefixed_columns(left_blocked, "left", key_columns).merge(
        prefixed_columns(right_blocked, "right", key_columns),
        how="outer",
        on=["entry_block_rule", *key_columns],
        indicator=True,
    )
    rows: list[dict[str, Any]] = []
    for _, row in joined.iterrows():
        merge_status = str(row["_merge"])
        status = {
            "left_only": "blocked_removed",
            "right_only": "blocked_added",
            "both": "blocked_common",
        }[merge_status]
        left_pnl = (
            float(row.get("left_adjusted_pnl", 0.0) or 0.0)
            if merge_status != "right_only"
            else 0.0
        )
        right_pnl = (
            float(row.get("right_adjusted_pnl", 0.0) or 0.0)
            if merge_status != "left_only"
            else 0.0
        )
        output: dict[str, Any] = {
            "entry_block_rule": rule,
            "blocked_status": status,
            "left_blocked_pnl": left_pnl,
            "right_blocked_pnl": right_pnl,
            "blocked_pnl_delta": right_pnl - left_pnl,
        }
        for column in key_columns:
            output[column] = row[column]
        for column in context_columns:
            if column in output:
                continue
            output[column] = first_available(
                row,
                [f"right_{column}", f"left_{column}", column],
                default="missing",
            )
        for column in [
            "entry_timestamp",
            "adjusted_pnl",
            "selected_fixed_60m_pred_pnl",
            "selected_fixed_60m_actual_pnl",
            "selected_loss_first_prob",
            "pred_side_confidence_gap",
            "pred_taken_ev",
        ]:
            output[f"left_{column}"] = row.get(f"left_{column}", np.nan)
            output[f"right_{column}"] = row.get(f"right_{column}", np.nan)
        rows.append(output)
    return pd.DataFrame(rows)


def summarize_rows(
    frame: pd.DataFrame,
    *,
    group_columns: list[str],
    status_column: str,
    value_column: str,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[*group_columns, status_column, "row_count", f"{value_column}_sum"]
        )
    return (
        frame.groupby([*group_columns, status_column], dropna=False)
        .agg(
            row_count=(value_column, "size"),
            **{f"{value_column}_sum": (value_column, "sum")},
            left_pnl_sum=("left_adjusted_pnl", "sum")
            if "left_adjusted_pnl" in frame.columns
            else (value_column, "sum"),
            right_pnl_sum=("right_adjusted_pnl", "sum")
            if "right_adjusted_pnl" in frame.columns
            else (value_column, "sum"),
        )
        .reset_index()
        .sort_values([*group_columns, f"{value_column}_sum"], ascending=True)
    )


def run_trade_set_delta(args: argparse.Namespace) -> Path:
    key_columns = parse_csv(args.key_columns)
    rules = parse_csv(args.entry_block_rules)
    context_columns = parse_csv(args.context_columns)
    left = read_trade_set(
        args.left_trades,
        label=args.left_label,
        key_columns=key_columns,
        entry_block_rules=rules,
        selector_variant_contains=args.selector_variant_contains,
    )
    right = read_trade_set(
        args.right_trades,
        label=args.right_label,
        key_columns=key_columns,
        entry_block_rules=rules,
        selector_variant_contains=args.selector_variant_contains,
    )

    delta_frames: list[pd.DataFrame] = []
    blocked_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for rule in rules:
        delta_rows, summary = compare_rule_trade_sets(
            left,
            right,
            key_columns=key_columns,
            context_columns=context_columns,
            rule=rule,
        )
        blocked_rows = compare_blocked_sets(
            left,
            right,
            key_columns=key_columns,
            context_columns=context_columns,
            rule=rule,
        )
        delta_frames.append(delta_rows)
        blocked_frames.append(blocked_rows)
        summary_rows.append(summary)

    delta = pd.concat(delta_frames, ignore_index=True) if delta_frames else pd.DataFrame()
    blocked = pd.concat(blocked_frames, ignore_index=True) if blocked_frames else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)

    run_dir = make_run_dir(args.output_dir, args.label)
    delta.to_csv(run_dir / "trade_set_delta_rows.csv", index=False)
    blocked.to_csv(run_dir / "blocked_set_delta_rows.csv", index=False)
    summary.to_csv(run_dir / "trade_set_delta_summary.csv", index=False)
    summarize_rows(
        delta,
        group_columns=[
            column
            for column in ["entry_block_rule", "role", "month"]
            if column in delta.columns
        ],
        status_column="change_status",
        value_column="delta_adjusted_pnl",
    ).to_csv(run_dir / "trade_set_delta_by_role_month.csv", index=False)
    summarize_rows(
        delta,
        group_columns=[
            column
            for column in [
                "entry_block_rule",
                "role",
                "direction",
                "combined_regime",
                "session_regime",
            ]
            if column in delta.columns
        ],
        status_column="change_status",
        value_column="delta_adjusted_pnl",
    ).to_csv(run_dir / "trade_set_delta_by_context.csv", index=False)
    if not blocked.empty:
        blocked.groupby(
            [
                column
                for column in ["entry_block_rule", "blocked_status", "role", "month"]
                if column in blocked.columns
            ],
            dropna=False,
        ).agg(
            row_count=("blocked_pnl_delta", "size"),
            left_blocked_pnl_sum=("left_blocked_pnl", "sum"),
            right_blocked_pnl_sum=("right_blocked_pnl", "sum"),
            blocked_pnl_delta_sum=("blocked_pnl_delta", "sum"),
        ).reset_index().to_csv(
            run_dir / "blocked_set_delta_by_role_month.csv",
            index=False,
        )
    else:
        pd.DataFrame().to_csv(run_dir / "blocked_set_delta_by_role_month.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "left_trades": args.left_trades,
                "right_trades": args.right_trades,
                "left_label": args.left_label,
                "right_label": args.right_label,
                "selector_variant_contains": args.selector_variant_contains,
                "entry_block_rules": rules,
                "key_columns": key_columns,
                "context_columns": context_columns,
            },
            indent=2,
            default=local_json_default,
        ),
        encoding="utf-8",
    )

    print("Trade set delta summary:")
    print(
        summary[
            [
                "entry_block_rule",
                "left_kept_pnl",
                "right_kept_pnl",
                "delta_pnl",
                "left_kept_count",
                "right_kept_count",
                "added_count",
                "removed_count",
                "common_changed_count",
                "left_blocked_count",
                "right_blocked_count",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left-trades", type=Path, required=True)
    parser.add_argument("--right-trades", type=Path, required=True)
    parser.add_argument("--left-label", default="left")
    parser.add_argument("--right-label", default="right")
    parser.add_argument("--selector-variant-contains", default="")
    parser.add_argument("--entry-block-rules", default=DEFAULT_RULES)
    parser.add_argument("--key-columns", default=DEFAULT_KEY_COLUMNS)
    parser.add_argument("--context-columns", default=DEFAULT_CONTEXT_COLUMNS)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_trade_set_delta_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_trade_set_delta(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
